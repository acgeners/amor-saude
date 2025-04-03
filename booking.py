# 🗂 Bibliotecas
import re

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


def preencher_paciente(driver, wait, cpf, data_nascimento, celular):
    try:
        print("🟢 Iniciando preenchimento de paciente...")

        if not abrir_select2_paciente(driver, wait, cpf):
            return False

        print("🔸 Aguardando opções visíveis diferentes de 'searching'...")
        max_tentativas = 4
        for tentativas in range(max_tentativas):
            opcoes = driver.find_elements(By.CSS_SELECTOR, "ul.select2-results__options li")
            opcoes_visiveis = [op for op in opcoes if op.is_displayed() and op.text.strip()]

            print(f"🔍 Tentativa {tentativas + 1} — {len(opcoes_visiveis)} opção(ões) visível(is):")
            for i, op in enumerate(opcoes_visiveis):
                texto = op.text.strip()
                # html = op.get_attribute("innerHTML")
                print(f"  ▶️ [{i}] Texto: {texto}")
                # print(f"     HTML: {html[:300]}{'...' if len(html) > 300 else ''}")

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
        print(f"🔍 Primeira opção final: {texto_opcao}")
        # print(f"🖱️ HTML do item que será clicado:\n{primeira_opcao.get_attribute('outerHTML')}")

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

        # 📅 Data de nascimento
        if data_nascimento:
            # Expressão regular para capturar dd/mm/yyyy
            padrao_data = r"\d{2}/\d{2}/\d{4}"

            # Se achar a data dentro do texto, pula o preenchimento
            if re.search(padrao_data, texto_opcao):
                print("Data de nascimento já presente no texto do paciente. Pulando preenchimento...")
            else:
                try:
                    # Aguarda até que o input esteja visível
                    input_nascimento = wait.until(EC.visibility_of_element_located((By.ID, "ageNascimento")))
                    print(f"Imput data de nascimento: {input_nascimento.text}")
                    if not input_nascimento.get_attribute("value").strip():
                        input_nascimento.clear()
                        input_nascimento.send_keys(data_nascimento)
                        print(f"📅 Data de nascimento preenchida: {data_nascimento}")
                except Exception as e:
                    print(f"⚠️ Erro ao preencher data de nascimento: {e}")

        # 📱 Celular
        if celular:
            try:
                input_celular = wait.until(EC.visibility_of_element_located((By.ID, "ageCel1")))
                if not input_celular.get_attribute("value").strip():
                    input_celular.clear()
                    input_celular.send_keys(celular)
                    print(f"📱 Celular preenchido: {celular}")
            except Exception as e:
                print(f"⚠️ Erro ao preencher celular: {e}")

        # 📨 Subcanal
        try:
            select_subcanal = Select(wait.until(EC.visibility_of_element_located((By.ID, "SubCanal"))))
            # Imprime o valor atualmente selecionado
            valor_atual = select_subcanal.first_selected_option.text.strip()
            print(f"Valor atual do Subcanal: '{valor_atual}'")

            # Imprime todas as opções disponíveis
            for option in select_subcanal.options:
                print(f"Opção encontrada: '{option.text.strip()}'")

            # Se a opção atual indicar que nenhuma opção foi selecionada, seleciona a opção que contenha "whatsapp"
            if "selecione" in valor_atual.lower():
                opcao_encontrada = False
                for option in select_subcanal.options:
                    texto_opcao = option.text.lower().strip()
                    # Ajuste aqui para corresponder ao que realmente aparece no HTML ("whatspp", "whatsapp", etc.)
                    if "whatspp" in texto_opcao or "whatsapp" in texto_opcao:
                        select_subcanal.select_by_visible_text(option.text)
                        print(f"📨 Subcanal selecionado: {option.text}")
                        opcao_encontrada = True
                        break
                if not opcao_encontrada:
                    print("⚠️ Não foi encontrada nenhuma opção contendo 'whatspp' ou 'whatsapp'.")
        except Exception as e:
            print(f"⚠️ Erro ao selecionar subcanal: {e}")

        # 📑 Tabela/Parceria
        try:
            tabela_select = wait.until(EC.element_to_be_clickable((By.ID, "ageTabela")))
            tabela_select.click()
            select_tabela = Select(tabela_select)
            select_tabela.select_by_visible_text("PARTICULAR*")
            print("📑 Tabela/Parceria selecionada.")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao selecionar Tabela/Parceria: {e}")

        # 🩺 Procedimento
        # Etapa B - Procedimento

        max_tentativas = 3
        for tentativa in range(max_tentativas):
            try:
                procedimento_container = wait.until(EC.element_to_be_clickable((
                    By.XPATH,
                    "//div[@id='divAgendamentoCheckin']//span[contains(@class, 'select2-selection') and contains(@class, 'select2-selection--single')]"
                )))

                print("🖱️ Container de Procedimento encontrado. Clicando para abrir dropdown...")
                # Rola a tela para que o elemento fique visível
                driver.execute_script("arguments[0].scrollIntoView(true);", procedimento_container)
                time.sleep(1)  # Pequeno delay para estabilizar a rolagem
                procedimento_container.click()

                print("🔸 Aguardando opções visíveis diferentes de 'searching'...")

                for espera in range(10):
                    opcoes = driver.find_elements(By.CSS_SELECTOR, "ul.select2-results__options li")
                    opcoes_visiveis = [op.text.strip() for op in opcoes if op.is_displayed() and op.text.strip()]

                    print(f"🔍 Tentativa {tentativa + 1} — {len(opcoes_visiveis)} opção(ões) visível(is):")

                    for i, texto in enumerate(opcoes_visiveis):
                        print(f"  ▶️ [{i}] Texto: {texto}")

                    if opcoes_visiveis:
                        primeiro_texto = opcoes_visiveis[0].lower()
                        if "searching" not in primeiro_texto:
                            break

                    time.sleep(0.5)
                else:
                    print("⛔ Nenhuma opção válida apareceu após aguardar.")
                    return False

                print("🔸 Rebuscando lista final de opções...")
                opcoes = driver.find_elements(By.CSS_SELECTOR, "ul.select2-results__options li")
                index_consulta = -1
                for idx, op in enumerate(opcoes):
                    if op.is_displayed():
                        texto = op.text.strip().lower()
                        if "consulta" in texto:
                            index_consulta = idx
                            break

                if index_consulta == -1:
                    print("⛔ Nenhuma opção contendo 'consulta' foi encontrada.")
                    return False

                # Rebuscar o elemento para evitar stale reference
                opcoes = driver.find_elements(By.CSS_SELECTOR, "ul.select2-results__options li")
                opcao_alvo = opcoes[index_consulta]
                texto_final = opcao_alvo.text.strip()
                opcao_alvo.click()
                print(f"✅ Procedimento selecionado: {texto_final}")

                # Se tudo ocorreu sem exceção, saia do loop de retry
                break

            except Exception as e:
                print(f"⛔ Erro ao selecionar Procedimento: {e}")
                return False

        else:
            print("⛔ Falha ao selecionar o procedimento após várias tentativas.")
            return False

        print("✅ Preenchimento de paciente concluído.")
        return True

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
        print(f"🔎 CPF digitado: {cpf}")

        return True

    except Exception as e:
        print(f"❌ Erro ao abrir select2 do paciente: {e}")
        return False


def confirmar_agendamento(driver, wait):
    try:
        # Aguarda o botão "Salvar" ficar clicável, rola até ele e realiza o clique
        botao_salvar = wait.until(EC.element_to_be_clickable((By.ID, "btnSalvarAgenda")))
        driver.execute_script("arguments[0].scrollIntoView(true);", botao_salvar)
        botao_salvar.click()
        print("✅ Clique no botão 'Salvar' realizado.")

        # Verifica se aparece um pop-up de erro logo após clicar (aguarda até 5 segundos)
        try:
            erro_popup = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.ui-pnotify.alert-danger"))
            )
            titulo_erro = erro_popup.find_element(By.CSS_SELECTOR, "h4.ui-pnotify-title").text
            mensagem_erro = erro_popup.find_element(By.CSS_SELECTOR, "div.ui-pnotify-text").text
            print("⛔ Erro ao salvar agendamento:")
            print("   Título:", titulo_erro)
            print("   Mensagem:", mensagem_erro)
            return False
        except TimeoutException:
            # Caso não apareça erro, prossegue com o fluxo
            pass

        # Aguarda a aparição do pop-up de sucesso
        try:
            pop_up_sucesso = wait.until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, "div.alert.ui-pnotify-container.alert-success")
                )
            )
            titulo_sucesso = pop_up_sucesso.find_element(By.CSS_SELECTOR, "h4.ui-pnotify-title").text
            print("✅ Pop-up de sucesso detectado:", titulo_sucesso)
        except TimeoutException:
            print("⚠️ Pop-up de sucesso não apareceu.")

        # # Verifica na listagem se o agendamento foi realizado (ajuste o XPath conforme necessário)
        # try:
        #     novo_agendamento = wait.until(
        #         EC.visibility_of_element_located((
        #             By.XPATH,
        #             "//table[@id='listaAgendamentos']//tr[td[contains(text(),'Consulta')]]"
        #         ))
        #     )
        #     print("✅ Agendamento encontrado na lista:", novo_agendamento.text)
        # except TimeoutException:
        #     print("⛔ Agendamento não foi listado na página.")
        #     return False

        return True

    except TimeoutException:
        print("⛔ Botão 'Salvar' não apareceu a tempo.")
        return False
    except Exception as e:
        print(f"❌ Erro ao tentar clicar no botão 'Salvar': {e}")
        return False

# def confirmar_agendamento(driver, wait):
#     try:
#         # Aguarda o botão ficar disponível e clicável
#         botao_salvar = wait.until(EC.element_to_be_clickable((By.ID, "btnSalvarAgenda")))
#         driver.execute_script("arguments[0].scrollIntoView(true);", botao_salvar)
#         botao_salvar.click()
#         print("✅ Clique no botão 'Salvar' realizado.")
#
#         try:
#             # Aguarda até que o pop-up de erro esteja visível (tempo máximo de 10 segundos)
#             erro_popup = wait.until(
#                 EC.visibility_of_element_located((By.CSS_SELECTOR, "div.ui-pnotify.alert-danger"))
#             )
#
#             # Extrai o título do erro e a mensagem
#             titulo_erro = erro_popup.find_element(By.CSS_SELECTOR, "h4.ui-pnotify-title").text
#             mensagem_erro = erro_popup.find_element(By.CSS_SELECTOR, "div.ui-pnotify-text").text
#
#             print("Título do Erro:", titulo_erro)
#             print("Mensagem do Erro:", mensagem_erro)
#         except Exception as e:
#             print("Pop-up de erro não encontrado:", e)
#
#         # Aguarda feedback da página
#         wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "modal-content")))
#         print("✅ Modal de agendamento fechado. Agendamento provavelmente concluído.")
#         return True
#
#     except TimeoutException:
#         print("⛔ Botão 'Salvar' não apareceu a tempo.")
#         return False
#     except Exception as e:
#         print(f"❌ Erro ao tentar clicar no botão 'Salvar': {e}")
#         return False





