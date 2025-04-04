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

# # 📆 Horários e datas
# from date_times import extrair_horarios_de_bloco

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
        logger.warning(f"⚠️ Não foi possível extrair o consultório ({type(e).__name__})")
        return None


def buscar_bloco_do_profissional(blocos, nome_profissional: str, especialidade: str):
    """
    Busca o bloco do profissional específico, com a especialidade e horário desejado.
    Retorna o bloco correspondente ou None.
    """
    time.sleep(1.5)
    for bloco in blocos:
        resultados = []
        max_tentativas = 3
        for tentativa in range(max_tentativas):
            try:
                painel = bloco.find_elements(By.CSS_SELECTOR, ".panel-title")
                if painel:
                    linhas = painel[0].text.strip().split("\n")
                    nome_bloco = linhas[0].strip()
                    especialidade_bloco = linhas[1].strip() if len(linhas) > 1 else ""
                    # print(f"🔍 Tentativa {tentativa + 1}: Encontrado -> {nome_bloco} | {especialidade_bloco}")
                    resultados.append((nome_bloco, especialidade_bloco))
                else:
                    # print(f"🔍 Tentativa {tentativa + 1}: Painel não encontrado.")
                    resultados.append((None, None))

            except Exception as e:
                print(f"⚠️ Erro na tentativa {tentativa + 1} ({type(e).__name__}): {e}")
                resultados.append((None, None))

            time.sleep(0.5)  # Pequena pausa entre as tentativas

        # Após 3 tentativas, verifica os resultados coletados
        for nome_bloco, especialidade_bloco in resultados:
            print(f"🔍 Profissional encontrado -> {nome_bloco} | {especialidade_bloco}")
            if nome_bloco is None:
                continue
            if nome_bloco.lower() == nome_profissional.lower() and especialidade.lower() in especialidade_bloco.lower():
                print("✅ Bloco encontrado com os critérios desejados.")
                return bloco

        print("⛔ Nenhum profissional com os critérios foi encontrado nesse bloco.")

    return None

def preencher_paciente(driver, wait, cpf, matricula, data_nascimento, celular):
    try:
        print("🟢 Iniciando preenchimento de paciente...")

        if not abrir_select2_paciente(driver, wait, cpf):
            return False

        print("🔸 Aguardando opções visíveis diferentes de 'searching'...")
        time.sleep(1)
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

            time.sleep(1)
        else:
            print("⛔ Nenhuma opção válida apareceu após aguardar.")
            return False

        print("🔸 Rebuscando lista final de opções...")
        opcoes = driver.find_elements(By.CSS_SELECTOR, "ul.select2-results__options li")
        opcoes_visiveis = [op for op in opcoes if op.is_displayed() and op.text.strip()]
        time.sleep(1)
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
# ___________________________________________________________________________________________________________________
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
                    time.sleep(1)
                    input_nascimento = wait.until(EC.visibility_of_element_located((By.ID, "ageNascimento")))
                    if not input_nascimento.get_attribute("value").strip():
                        input_nascimento.clear()
                        input_nascimento.send_keys(data_nascimento)
                        print(f"📅 Data de nascimento preenchida: {data_nascimento}")
                except Exception as e:
                    print(f"⚠️ Erro ao preencher data de nascimento ({type(e).__name__})")
# ___________________________________________________________________________________________________________________
        # 📱 Celular
        if celular:
            try:
                time.sleep(1)
                input_celular = wait.until(EC.visibility_of_element_located((By.ID, "ageCel1")))
                if not input_celular.get_attribute("value").strip():
                    input_celular.clear()
                    input_celular.send_keys(celular)
                    print(f"📱 Celular preenchido: {celular}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao preencher celular ({type(e).__name__})")
# ___________________________________________________________________________________________________________________
        # 📨 Subcanal
        try:
            select_subcanal = Select(wait.until(EC.visibility_of_element_located((By.ID, "SubCanal"))))
            # Imprime o valor atualmente selecionado
            valor_atual = select_subcanal.first_selected_option.text.strip()
            print(f"Valor atual do Subcanal: '{valor_atual}'")

            # # Imprime todas as opções disponíveis
            # for option in select_subcanal.options:
            #     print(f"Opção encontrada: '{option.text.strip()}'")

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
                    return False
        except Exception as e:
            logger.warning(f"⚠️ Erro ao selecionar subcanal ({type(e).__name__})")
            return False
#___________________________________________________________________________________________________________________
        if matricula:
            # 📑 Tabela/Parceria
            try:
                tabela_select = wait.until(EC.element_to_be_clickable((By.ID, "ageTabela")))
                tabela_select.click()
                select_tabela = Select(tabela_select)
                select_tabela.select_by_visible_text("Cartão de TODOS*")
                print("📑 Tabela/Parceria definida como 'Cartão de TODOS*'.")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao selecionar Tabela/Parceria ({type(e).__name__})")

            # 🪪 Matricula
            try:
                input_matricula = wait.until(EC.visibility_of_element_located((By.ID, "ageCel1")))
                if not input_matricula.get_attribute("value").strip():
                    input_matricula.clear()
                    input_matricula.send_keys(matricula)
                    print(f"🪪 Matricula preenchido: {matricula}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao preencher matricula ({type(e).__name__})")

        else:
            try:
                tabela_select = wait.until(EC.element_to_be_clickable((By.ID, "ageTabela")))
                tabela_select.click()
                select_tabela = Select(tabela_select)
                select_tabela.select_by_visible_text("PARTICULAR*")
                print("📑 Tabela/Parceria definida como 'PARTICULAR*'.")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao selecionar Tabela/Parceria ({type(e).__name__})")
# ___________________________________________________________________________________________________________________
        # 🩺 Procedimento

        time.sleep(1)
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
                    opcoes_visiveis = [op.text.strip() for op in opcoes if
                                       op.is_displayed() and op.text.strip()]

                    print(f"🔍 Tentativa {tentativa + 1} — {len(opcoes_visiveis)} opção(ões) visível(is):")
                    time.sleep(1)

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
                return True

            except Exception as e:
                print(f"⛔ Erro ao selecionar Procedimento ({type(e).__name__})")
                return False

        else:
            print("⛔ Falha ao selecionar o procedimento após várias tentativas.")
            return False
        # ___________________________________________________________________________________________________________________


    except Exception as e:
        print(f"❌ Erro ao preencher o paciente ({type(e).__name__})")
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
        print(f"❌ Erro ao cadastrar paciente ({type(e).__name__})")
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
        print(f"❌ Erro ao abrir select2 do paciente ({type(e).__name__})")
        return False


def salvar_agendamento(driver, wait):
    try:
        # Aguarda o botão "Salvar" ficar clicável, rola até ele e realiza o clique
        botao_salvar = wait.until(EC.element_to_be_clickable((By.ID, "btnSalvarAgenda")))
        driver.execute_script("arguments[0].scrollIntoView(true);", botao_salvar)
        botao_salvar.click()
        print("✅ Clique no botão 'Salvar' realizado.")
        return True

    except TimeoutException:
        print("⛔ Botão 'Salvar' não apareceu a tempo.")
        return False
    except Exception as e:
        print(f"❌ Erro ao tentar clicar no botão 'Salvar' ({type(e).__name__})")
        return False


def confirmar_agendado(driver, wait, nome_paciente, nome_medico, hora, especialidade):
        # Verifica na listagem se o agendamento foi realizado
        try:
            checkbox = wait.until(EC.presence_of_element_located((By.ID, "HVazios")))
            driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)

            # Verifica se o checkbox está marcado
            if checkbox.is_selected():
                driver.execute_script("arguments[0].click();", checkbox)
                time.sleep(1)
                print("☑️ Checkbox 'Somente horários vazios' desmarcada.")
            else:
                print("☑️ Checkbox 'Somente horários vazios' já estava desmarcada.")

        except TimeoutException:
            print("⚠️ Checkbox não encontrada.")
            return False

        blocos = driver.find_elements(By.CSS_SELECTOR, "td[id^='pf']")
        bloco_desejado = buscar_bloco_do_profissional(blocos, nome_medico, especialidade)

        if not bloco_desejado:
            print("⛔ Horário desejado com o profissional especificado não encontrado.")
            return False
        hora_id = hora.replace(":", "")
        try:
            tr_horario = bloco_desejado.find_element(By.CSS_SELECTOR, f"tr[data-id='{hora_id}']")
            botao = tr_horario.find_element(By.CSS_SELECTOR, "button.btn.btn-xs.btn-warning.slot-cor")
            driver.execute_script("arguments[0].scrollIntoView(true);", botao) # TODO Não precisa necessariamente

            # Verifica se o botão está clicável (habilitado e visível) # TODO Não precisa necessariamente
            if botao.is_enabled() and botao.is_displayed():
                print(f"\n✅ Horário encontrado: {hora} com {nome_medico}")
            else:
                logger.warning("❌ Botão do horário não está clicável.")
                return False

        except Exception as e:
            logger.warning(f"❌ Erro ao localizar o botão do horário ({type(e).__name__})")
            return False

        try:
            # Verifica se o nome do paciente consta nessa linha
            if nome_paciente in tr_horario.text:
                print(f"✅ Agendamento confirmado: {tr_horario.text}")
                return True
            else:
                print("⛔ Agendamento não encontrado: nome do paciente não confere.")
                return False

        except Exception as e:
            print("⛔ Erro ao verificar o agendamento:", type(e).__name__)
            return False


def cancelar_agendado(driver, wait, nome_paciente, nome_medico, hora, especialidade):
    # Verifica na listagem se o agendamento foi realizado
    try:
        checkbox = wait.until(EC.presence_of_element_located((By.ID, "HVazios")))
        driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)

        # Verifica se o checkbox está marcado
        if checkbox.is_selected():
            driver.execute_script("arguments[0].click();", checkbox)
            time.sleep(1)
            print("☑️ Checkbox 'Somente horários vazios' desmarcada.")
        else:
            print("☑️ Checkbox 'Somente horários vazios' já estava desmarcada.")

    except TimeoutException:
        print("⚠️ Checkbox não encontrada.")
        return False

    blocos = driver.find_elements(By.CSS_SELECTOR, "td[id^='pf']")
    bloco_desejado = buscar_bloco_do_profissional(blocos, nome_medico, especialidade)

    if not bloco_desejado:
        print("⛔ Horário agendado com o profissional especificado não encontrado.")
        return False
    hora_id = hora.replace(":", "")
    try:
        tr_horario = bloco_desejado.find_element(By.CSS_SELECTOR, f"tr[data-id='{hora_id}']")
        botao = tr_horario.find_element(By.CSS_SELECTOR, "button.btn.btn-xs.btn-warning.slot-cor")
        driver.execute_script("arguments[0].scrollIntoView(true);", botao)  # TODO Não precisa necessariamente

        # Verifica se o botão está clicável (habilitado e visível) # TODO Não precisa necessariamente
        if botao.is_enabled() and botao.is_displayed():
            print(f"\n✅ Horário encontrado: {hora} com {nome_medico}")
        else:
            logger.warning("❌ Botão do horário não está clicável.")
            return False

    except Exception as e:
        logger.warning(f"❌ Erro ao localizar o botão do horário ({type(e).__name__})")
        return False

    try:
        # Verifica se o nome do paciente consta nessa linha
        if nome_paciente in tr_horario.text:
            print(f"✅ Agendamento confirmado: {tr_horario.text}")
            return True
        else:
            print("⛔ Agendamento não encontrado: nome do paciente não confere.")
            return False

    except Exception as e:
        print("⛔ Erro ao verificar o agendamento:", type(e).__name__)
        return False