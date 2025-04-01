# 🗂 Bibliotecas
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from datetime import datetime
from typing import Optional

# 📆 Horários e datas
from date_times import navegar_para_data, extrair_horarios_de_bloco

# 🧭 Navegador
from driver_utils import get_driver, driver_lock

# 🔐 Sessão e login
from auth_utils import sessao_ja_logada, fazer_login

# 💾 Redis
# from redis_utils import recuperar_agendamento


def extrair_consultorio_do_bloco(bloco) -> Optional[str]:
    try:
        # Sobe no DOM para encontrar a TR pai, depois sobe até o TR anterior com a classe nomeProf
        tr_bloco = bloco.find_element(By.XPATH, "./ancestor::tr[1]")
        tr_consultorio = tr_bloco.find_element(By.XPATH, "preceding-sibling::tr[td[contains(@class, 'nomeProf')]]")
        texto = tr_consultorio.text.strip()
        if texto:
            return texto.split("\n")[0]  # Em geral, só queremos a linha com o nome do consultório
    except Exception as e:
        print(f"⚠️ Não foi possível extrair o consultório: {e}")
    return None


def buscar_bloco_do_profissional(blocos, nome_profissional: str, especialidade: str, hora: str):
    """
    Busca o bloco do profissional específico, com a especialidade e horário desejado.
    Retorna o bloco correspondente ou None.
    """
    for bloco in blocos:
        try:
            painel = bloco.find_elements(By.CSS_SELECTOR, ".panel-title")
            if not painel:
                continue

            linhas = painel[0].text.strip().split("\n")
            nome_bloco = linhas[0].strip()
            especialidade_bloco = linhas[1].strip() if len(linhas) > 1 else ""

            print(f"🔍 Profissional encontrado: {nome_bloco} | {especialidade_bloco}")

            # Verifica se é o profissional e especialidade corretos
            if nome_bloco.lower() != nome_profissional.lower():
                continue
            if especialidade.lower() not in especialidade_bloco.lower():
                continue

            # Verifica se o horário desejado está disponível
            horarios_disponiveis = extrair_horarios_de_bloco(bloco, especialidade)
            if hora in horarios_disponiveis:
                return bloco

        except Exception as e:
            print(f"⚠️ Erro ao analisar bloco: {e}")
            continue

    return None


def preencher_paciente(driver, wait, cpf):
    try:
        # Clica no select2 para ativar o campo de busca
        campo_paciente = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "span.select2-selection--single")))
        campo_paciente.click()

        # Encontra o campo de input do select2
        input_paciente = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input.select2-search__field")))
        input_paciente.send_keys(cpf)
        print(f"🔎 Buscando paciente com CPF: {cpf}")

        # Aguarda a lista de sugestões aparecer
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.select2-results__options li")))
        opcoes = driver.find_elements(By.CSS_SELECTOR, "ul.select2-results__options li")

        if not opcoes:
            print("⛔ Nenhuma sugestão de paciente encontrada.")
            return False

        # Clica na primeira opção
        opcoes[0].click()
        print("✅ Paciente selecionado.")
        return True

    except TimeoutException:
        print("⛔ Tempo excedido ao tentar preencher o paciente.")
        return False
    except Exception as e:
        print(f"❌ Erro ao preencher o paciente: {e}")
        return False


def confirmar_agendamento(driver, wait):
    try:
        # Aguarda o botão ficar disponível e clicável
        botao_salvar = wait.until(EC.element_to_be_clickable((By.ID, "btnSalvarAgenda")))
        driver.execute_script("arguments[0].scrollIntoView(true);", botao_salvar)
        botao_salvar.click()
        print("✅ Clique no botão 'Salvar' realizado.")

        # Aguarda feedback da página
        wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "modal-content")))
        print("✅ Modal de agendamento fechado. Agendamento provavelmente concluído.")
        return True

    except TimeoutException:
        print("⛔ Botão 'Salvar' não apareceu a tempo.")
        return False
    except Exception as e:
        print(f"❌ Erro ao tentar clicar no botão 'Salvar': {e}")
        return False


async def agendar_horario(solicitante_id: str, nome_medico: str, especialidade: str, data: str, hora: str,
                          nome_paciente: str, cpf: str, data_nascimento: str, contato: str):
    async with driver_lock:
        driver = get_driver()
        wait = WebDriverWait(driver, 20)

        # Valida e converte data para datetime
        try:
            data_dt = datetime.strptime(data, "%d/%m/%Y")
        except ValueError:
            print("⚠️ Data em formato inválido.")
            return None

        # TODO vai usar pra alguma coisa?
        # # Buscar dados no Redis para garantir que esse horário estava reservado
        # dados_reserva = recuperar_agendamento(solicitante_id, especialidade, data, hora)
        # if not dados_reserva:
        #     print("⛔ Dados não encontrados no Redis. Pode ter expirado.")
        #     return None

        try:
            driver.get("https://amor-saude.feegow.com/pre-v7.6/?P=AgendaMultipla&Pers=1")

            if not sessao_ja_logada(driver):
                print("🔐 Sessão não ativa. Realizando login...")
                fazer_login(driver, wait)
            else:
                print("🔓 Sessão já autenticada.")

            if not navegar_para_data(driver, wait, data_dt):
                print("⛔ Falha ao navegar para a data desejada.")
                return None

            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-hover")))
                print("✅ Tabela de horários apareceu.")
            except TimeoutException:
                print("⛔ Tabela não apareceu após seleção. Pulando para próxima data.")

            # Garante visibilidade da grade
            driver.execute_script("""
                                        const el = document.getElementById('contQuadro');
                                        if (el) {
                                            el.scrollLeft = el.scrollWidth;
                                        }
                                    """)

            blocos = driver.find_elements(By.CSS_SELECTOR, "td[id^='pf']")
            bloco_desejado = buscar_bloco_do_profissional(blocos, nome_medico, especialidade, hora)


            if not bloco_desejado:
                print("⛔ Horário desejado com o profissional especificado não encontrado.")
                return None

            consultorio_desejado = extrair_consultorio_do_bloco(bloco_desejado)

            # Clica no botão correspondente ao horário
            try:
                tr_horario = bloco_desejado.find_element(By.CSS_SELECTOR, f"tr[data-hora='{hora}']")
                botao = tr_horario.find_element(By.CSS_SELECTOR, "button.btn-info")
                driver.execute_script("arguments[0].scrollIntoView(true);", botao)
                botao.click()
                print(f"✅ Clicado no horário {hora} com {nome_medico}")
            except Exception as e:
                print(f"❌ Erro ao localizar/clicar no botão do horário: {e}")
                return None

            print(f"Teste com: {especialidade}, {nome_medico}, {data}, {hora}, {nome_paciente}, {solicitante_id}, {data_nascimento}, "
                  f"{cpf}, {contato}.")

            if not preencher_paciente(driver, wait, cpf):
                return {"erro": "Não foi possível selecionar o paciente com o CPF informado."}

            if not confirmar_agendamento(driver, wait):
                return {"erro": "Não foi possível confirmar o agendamento."}

            return {
                "especialidade": especialidade,
                "nome_medico": nome_medico,
                # "consultorio": consultorio_desejado, TODO pode incluir isso?
                "data": data,
                "hora": hora,
                "paciente": nome_paciente,
                "status": "Agendamento concluído com sucesso"
            }

        except Exception as e:
            print(f"❌ Erro durante o processo de agendamento: {e}")
            return None