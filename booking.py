# 🗂 Bibliotecas
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from typing import Optional

# 📆 Horários e datas
from date_times import extrair_horarios_de_bloco


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


def cadastrar_paciente(driver, wait, nome_paciente, cpf, data_nascimento):
    try:
        # Espera e clica no botão "INSERIR"
        botao_inserir = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button.btn-inserir-si")
        ))
        botao_inserir.click()

        # Preenche os dados no modal
        wait.until(EC.visibility_of_element_located((By.ID, "modal-nome"))).send_keys(nome_paciente)
        driver.find_element(By.ID, "modal-cpf").send_keys(cpf)
        if data_nascimento:
            try:
                driver.find_element(By.ID, "modal-dataNascimento").send_keys(data_nascimento)
            except:
                print("⚠️ Campo de data de nascimento não encontrado (opcional).")

        # Clica em salvar
        botao_salvar = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button.components-modal-submit-btn")
        ))
        botao_salvar.click()

        print("✅ Paciente cadastrado com sucesso.")
        return True

    except Exception as e:
        print(f"❌ Erro ao cadastrar paciente: {e}")
        return False

