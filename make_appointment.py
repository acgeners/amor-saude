# 🗂 Bibliotecas
from fastapi import APIRouter
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from datetime import datetime
import logging

# 📑 Modelos e lifespan
from code_sup import ConfirmacaoAgendamento

# 📆 Horários e datas
from date_times import navegar_para_data

# 🧭 Navegador
from driver_utils import get_driver, driver_lock

# 🔐 Sessão e login
from auth_utils import sessao_ja_logada, fazer_login

# 📅 Agendamento
from booking import buscar_bloco_do_profissional, preencher_paciente, confirmar_agendamento, cadastrar_paciente
# extrair_consultorio_do_bloco,


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter()


async def agendar_horario(solicitante_id: str, nome_medico: str, especialidade: str, data: str, hora: str,
                          nome_paciente: str, cpf: str, data_nascimento: str, contato: str):
    async with driver_lock:
        driver = get_driver()
        wait = WebDriverWait(driver, 20)

        # Valida e converte data para datetime
        try:
            data_dt = datetime.strptime(data, "%d/%m/%Y")
        except ValueError as e:
            logger.warning(f"⚠️ Data inválida: {data} - {e}")
            return {"erro": "⚠️ Data em formato inválido."}

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
                logger.warning("⛔ Tabela não apareceu após seleção. Pulando para próxima data.")

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
                logger.warning("⛔ Horário desejado com o profissional especificado não encontrado.")
                return {"erro": "Horário desejado com o profissional especificado não encontrado."}

            # consultorio_desejado = extrair_consultorio_do_bloco(bloco_desejado) TODO ver se vai usar

            # Clica no botão correspondente ao horário
            try:
                tr_horario = bloco_desejado.find_element(By.CSS_SELECTOR, f"tr[data-hora='{hora}']")
                botao = tr_horario.find_element(By.CSS_SELECTOR, "button.btn-info")
                driver.execute_script("arguments[0].scrollIntoView(true);", botao)
                botao.click()
                print(f"✅ Clicado no horário {hora} com {nome_medico}")
            except Exception as e:
                logger.warning(f"❌ Erro ao localizar/clicar no botão do horário: {e}")
                return { "erro": "❌ Erro ao localizar/clicar no botão do horário: {e}"}

            print(f"Teste com: {especialidade}, {nome_medico}, {data}, {hora}, {nome_paciente}, {solicitante_id}, {data_nascimento}, "
                  f"{cpf}, {contato}.")

            if not preencher_paciente(driver, wait, cpf, data_nascimento, contato):
                print("⚠️ Tentando cadastrar o paciente...")

                if not cadastrar_paciente(driver, wait, nome_paciente, cpf):
                    return {"erro": "Paciente não encontrado e não foi possível cadastrá-lo."}

                # Aguarda fechamento do modal antes de tentar novamente
                wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "modal-content")))
                print("✅ Modal de cadastro fechado.")

                # Após cadastro, tenta selecionar o paciente novamente
                if not preencher_paciente(driver, wait, cpf, data_nascimento, contato):
                    return {"erro": "Paciente foi cadastrado, mas não pôde ser selecionado."}

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
            logger.exception(f"❌ Erro inesperado durante o processo de agendamento - {e}")
            return None


@router.post("/make_appointment")
async def make_appointment(body: ConfirmacaoAgendamento):
    dados = await agendar_horario(
        solicitante_id=body.solicitante_id,
        especialidade=body.especialidade,
        nome_medico=body.nome_profissional,
        data=body.data,
        hora=body.hora,
        nome_paciente=body.nome_paciente,
        cpf=body.CPF,
        data_nascimento=body.data_nascimento,
        contato=body.contato
    )

    if not dados:
        return {"erro": "Falha ao confirmar agendamento. Verifique os dados ou tente novamente."}

    return {"status": "confirmado", "detalhes": dados}
