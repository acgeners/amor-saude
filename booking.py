# 🗂 Bibliotecas
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import Select
from typing import Optional
import logging
import time

# 📆 Horários e datas
from date_times import extrair_horarios_de_bloco

logger = logging.getLogger(__name__)


def extrair_consultorio_do_bloco(bloco) -> Optional[str]:
    try:
        # Sobe no DOM para encontrar a TR pai, depois sobe até o TR anterior com a classe nomeProf
        tr_bloco = bloco.find_element(By.XPATH, "./ancestor::tr[1]")
        tr_consultorio = tr_bloco.find_element(By.XPATH, "preceding-sibling::tr[td[contains(@class, 'nomeProf')]]")
        texto = tr_consultorio.text.strip()
        if texto:
            return texto.split("\n")[0]  # Em geral, só queremos a linha com o nome do consultório
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível extrair o consultório - {e}")
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


# def preencher_paciente(driver, wait, cpf, data_nascimento, celular):
#     try:
#         print("🟢 Iniciando preenchimento de paciente...")
#
#         # Aguarda e rola até o campo do select2
#         # Dentro da função preencher_paciente:
#         print("🔸 Buscando campo select2 do paciente...")
#         campo_paciente = wait.until(
#             EC.visibility_of_element_located((
#                 By.CSS_SELECTOR,
#                 "span.select2-selection--single[aria-labelledby='select2-PacienteID-container']"
#             ))
#         )
#         driver.execute_script("arguments[0].scrollIntoView(true);", campo_paciente)
#         ActionChains(driver).move_to_element(campo_paciente).click().perform()
#         print("✅ Campo select2 do paciente clicado com sucesso.")
#
#         # Encontra o campo de input do select2
#         print("🔸 Buscando input para digitar o CPF...")
#         input_paciente = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input.select2-search__field")))
#         input_paciente.send_keys(cpf)
#         print(f"🔎 CPF digitado: {cpf}")
#
#         # Aguarda opções reais (não "Searching…")
#         print("🔸 Aguardando opções visíveis diferentes de 'searching'...")
#         max_tentativas = 10
#         for tentativas in range(max_tentativas):
#             opcoes = driver.find_elements(By.CSS_SELECTOR, "ul.select2-results__options li")
#             opcoes_visiveis = [op for op in opcoes if op.is_displayed() and op.text.strip()]
#
#             print(f"🔍 Tentativa {tentativas + 1} — {len(opcoes_visiveis)} opção(ões) visível(is):")
#             for i, op in enumerate(opcoes_visiveis):
#                 texto = op.text.strip()
#                 html = op.get_attribute("innerHTML")
#                 print(f"  ▶️ [{i}] Texto: {texto}")
#                 print(f"     HTML: {html[:300]}{'...' if len(html) > 300 else ''}")  # Limita o tamanho do HTML no log
#
#             if opcoes_visiveis:
#                 primeiro_texto = opcoes_visiveis[0].text.strip().lower()
#                 if "searching" not in primeiro_texto:
#                     break
#
#             time.sleep(0.5)
#         else:
#             print("⛔ Nenhuma opção válida apareceu após aguardar.")
#             return False
#
#         # Rebusca a lista final para evitar stale element
#         print("🔸 Rebuscando lista final de opções...")
#         opcoes = driver.find_elements(By.CSS_SELECTOR, "ul.select2-results__options li")
#         opcoes_visiveis = [op for op in opcoes if op.is_displayed() and op.text.strip()]
#         if not opcoes_visiveis:
#             print("⛔ Nenhuma opção visível final encontrada.")
#             return False
#
#         primeira_opcao = opcoes_visiveis[0]
#         texto_opcao = primeira_opcao.text.strip().lower()
#         html_opcao = primeira_opcao.get_attribute('innerHTML')
#         outer_html = primeira_opcao.get_attribute('outerHTML')
#         print(f"🔍 Primeira opção final (texto): {texto_opcao}")
#         print(f"🔍 Primeira opção final (HTML interno): {html_opcao[:300]}{'...' if len(html_opcao) > 300 else ''}")
#         print(f"🖱️ HTML do item que será clicado (outerHTML):\n{outer_html}")
#
#         # Verifica se a primeira opção é 'Nenhum resultado'
#         if "nenhum resultado" in texto_opcao:
#             print("⚠️ Primeira opção indica que o paciente não foi encontrado.")
#             return False
#
#         try:
#             botao_inserir = primeira_opcao.find_element(By.CLASS_NAME, "btn-inserir-si")
#             if botao_inserir.is_displayed():
#                 print("⚠️ Botão de inserir visível na primeira opção. Vai seguir para cadastro.")
#                 return False
#         except NoSuchElementException:
#             print("✅ Nenhum botão de inserir encontrado — é um paciente válido.")
#
#         # Clica na opção
#         print("🖱️ Clicando na opção do paciente...")
#         primeira_opcao.click()
#         print("✅ Paciente selecionado.")
#
#         # Preenche data de nascimento, se necessário
#         if data_nascimento:
#             print("🔸 Verificando campo de data de nascimento...")
#             input_nascimento = wait.until(EC.presence_of_element_located((By.ID, "ageNascimento")))
#             if not input_nascimento.get_attribute("value").strip():
#                 input_nascimento.clear()
#                 input_nascimento.send_keys(data_nascimento)
#                 print(f"📅 Data de nascimento preenchida: {data_nascimento}")
#             else:
#                 print("📅 Data de nascimento já estava preenchida.")
#
#         # Preenche celular, se necessário
#         if celular:
#             print("🔸 Verificando campo de celular...")
#             input_celular = driver.find_element(By.ID, "ageCel1")
#             if not input_celular.get_attribute("value").strip():
#                 input_celular.clear()
#                 input_celular.send_keys(celular)
#                 print(f"📱 Celular preenchido: {celular}")
#             else:
#                 print("📱 Celular já estava preenchido.")
#
#         # Seleciona subcanal "Whatsapp"
#         print("🔸 Verificando subcanal...")
#         try:
#             select_subcanal = Select(wait.until(EC.presence_of_element_located((By.ID, "SubCanal"))))
#             valor_atual = select_subcanal.first_selected_option.text.strip().lower()
#             if "selecione" in valor_atual:
#                 for option in select_subcanal.options:
#                     if "whatsapp" in option.text.lower():
#                         select_subcanal.select_by_visible_text(option.text)
#                         print(f"📨 Subcanal selecionado: {option.text}")
#                         break
#             else:
#                 print(f"📨 Subcanal já estava selecionado: {valor_atual}")
#         except Exception as e:
#             print(f"⚠️ Erro ao selecionar subcanal: {e}")
#
#         print("✅ Finalizado preenchimento de paciente com sucesso.")
#         return True
#
#     except TimeoutException:
#         print("⛔ Tempo excedido ao tentar preencher o paciente.")
#         return False
#     except Exception as e:
#         print(f"❌ Erro ao preencher o paciente: {e}")
#         return False


def preencher_paciente(driver, wait, cpf, data_nascimento, celular):
    try:
        print("🟢 Iniciando preenchimento de paciente...")

        if not abrir_select2_paciente(driver, wait, cpf):
            return False

        print("🔸 Aguardando opções visíveis diferentes de 'searching'...")
        max_tentativas = 10
        for tentativas in range(max_tentativas):
            opcoes = driver.find_elements(By.CSS_SELECTOR, "ul.select2-results__options li")
            opcoes_visiveis = [op for op in opcoes if op.is_displayed() and op.text.strip()]

            print(f"🔍 Tentativa {tentativas + 1} — {len(opcoes_visiveis)} opção(ões) visível(is):")
            for i, op in enumerate(opcoes_visiveis):
                texto = op.text.strip()
                html = op.get_attribute("innerHTML")
                print(f"  ▶️ [{i}] Texto: {texto}")
                print(f"     HTML: {html[:300]}{'...' if len(html) > 300 else ''}")

            if opcoes_visiveis:
                primeiro_texto = opcoes_visiveis[0].text.strip().lower()
                if "searching" not in primeiro_texto:
                    break

            time.sleep(0.5)
        else:
            print("⛔ Nenhuma opção válida apareceu após aguardar.")
            return False

        print("🔸 Rebuscando lista final de opções...")
        opcoes = driver.find_elements(By.CSS_SELECTOR, "ul.select2-results__options li")
        opcoes_visiveis = [op for op in opcoes if op.is_displayed() and op.text.strip()]
        if not opcoes_visiveis:
            print("⛔ Nenhuma opção visível final encontrada.")
            return False

        primeira_opcao = opcoes_visiveis[0]
        texto_opcao = primeira_opcao.text.strip().lower()
        print(f"🔍 Primeira opção final (texto): {texto_opcao}")
        print(f"🖱️ HTML do item que será clicado:\n{primeira_opcao.get_attribute('outerHTML')}")

        if "nenhum resultado" in texto_opcao:
            print("⚠️ Primeira opção indica que o paciente não foi encontrado.")
            return False

        try:
            botao_inserir = primeira_opcao.find_element(By.CLASS_NAME, "btn-inserir-si")
            if botao_inserir.is_displayed():
                print("⚠️ Botão de inserir visível. Paciente ainda não cadastrado.")
                return False
        except NoSuchElementException:
            print("✅ Nenhum botão de inserir — paciente existente.")

        primeira_opcao.click()
        print("✅ Paciente selecionado.")

        if data_nascimento:
            input_nascimento = wait.until(EC.presence_of_element_located((By.ID, "ageNascimento")))
            if not input_nascimento.get_attribute("value").strip():
                input_nascimento.clear()
                input_nascimento.send_keys(data_nascimento)
                print(f"📅 Data de nascimento preenchida: {data_nascimento}")

        if celular:
            input_celular = driver.find_element(By.ID, "ageCel1")
            if not input_celular.get_attribute("value").strip():
                input_celular.clear()
                input_celular.send_keys(celular)
                print(f"📱 Celular preenchido: {celular}")

        try:
            select_subcanal = Select(wait.until(EC.presence_of_element_located((By.ID, "SubCanal"))))
            valor_atual = select_subcanal.first_selected_option.text.strip().lower()
            if "selecione" in valor_atual:
                for option in select_subcanal.options:
                    if "whatsapp" in option.text.lower():
                        select_subcanal.select_by_visible_text(option.text)
                        print(f"📨 Subcanal selecionado: {option.text}")
                        break
        except Exception as e:
            print(f"⚠️ Erro ao selecionar subcanal: {e}")

        print("✅ Preenchimento de paciente concluído.")
        return True

    except TimeoutException:
        print("⛔ Tempo excedido ao tentar preencher o paciente.")
        return False
    except Exception as e:
        print(f"❌ Erro ao preencher o paciente: {e}")
        return False


def cadastrar_paciente(driver, wait, nome_paciente, cpf):
    try:
        print("🟢 Iniciando processo de cadastro de novo paciente...")

        if not abrir_select2_paciente(driver, wait, cpf):
            return False

        print("🔸 Aguardando botão INSERIR aparecer...")
        botao_inserir = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-inserir-si")))
        driver.execute_script("arguments[0].scrollIntoView(true);", botao_inserir)
        ActionChains(driver).move_to_element(botao_inserir).click().perform()
        print("🖱️ Botão INSERIR clicado.")

        input_nome = wait.until(EC.visibility_of_element_located((By.ID, "modal-nome")))
        input_nome.clear()
        input_nome.send_keys(nome_paciente)
        print(f"✍️ Nome preenchido: {nome_paciente}")

        input_cpf = wait.until(EC.visibility_of_element_located((By.ID, "modal-cpf")))
        input_cpf.clear()
        input_cpf.send_keys(cpf)
        print(f"🔢 CPF preenchido: {cpf}")

        botao_salvar = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.components-modal-submit-btn")))
        ActionChains(driver).move_to_element(botao_salvar).click().perform()
        print("💾 Botão SALVAR clicado.")

        print("✅ Formulário de cadastro de paciente enviado com sucesso.")
        return True

    except Exception as e:
        print(f"❌ Erro ao cadastrar paciente: {e}")
        return False


def abrir_select2_paciente(driver, wait, cpf):
    try:
        print("🟣 Abrindo campo de paciente e digitando CPF...")

        # Clica no campo do paciente (select2)
        campo_paciente = wait.until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "span.select2-selection--single[aria-labelledby='select2-PacienteID-container']"
            ))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", campo_paciente)
        ActionChains(driver).move_to_element(campo_paciente).click().perform()
        print("✅ Campo de paciente clicado.")

        # Digita o CPF
        input_paciente = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input.select2-search__field")
        ))
        input_paciente.clear()
        input_paciente.send_keys(cpf)
        print(f"🔎 CPF digitado no select2: {cpf}")

        return True

    except Exception as e:
        print(f"❌ Erro ao abrir select2 do paciente: {e}")
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





