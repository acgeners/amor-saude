# 🗂 Bibliotecas
import time

from fastapi import APIRouter
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from typing import Union, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from selenium.webdriver.support.wait import WebDriverWait
# import traceback
import logging

# 📑 Modelos e lifespan
from code_sup import RequisicaoHorario

# 🧭 Navegador
from driver_utils import get_driver, driver_lock

# 🔐 Sessão e login
from auth_utils import sessao_ja_logada, fazer_login

# 💾 Redis
from redis_utils import registrar_agendamento, ja_foi_enviado

# 📆 Horários e datas
from date_times import navegar_para_data, extrair_horarios_de_bloco

# 📅 Agendamento
# from booking import extrair_consultorio_do_bloco

# 📑 Modelos e lifespan
from code_sup import print_caixa


logger = logging.getLogger(__name__)
router = APIRouter()


async def buscar_primeiro_horario(especialidade: str, solicitante_id: str, data: Optional[str] = None,
                                  minutos_ate_disponivel: int = 0) -> Union[dict[str, str], None]:
    async with driver_lock:
        driver = get_driver()
        wait = WebDriverWait(driver, 20)
        # TODO só se der problema nas abas
        # garantir_aba_principal(driver)  # 🧠 Garante que estamos na aba certa

        if data:
            buscar_data = data
        else:
            buscar_data = datetime.today().strftime('%d/%m/%Y')  # ou outro formato que você usa

        print("\n🧭 Acessando AmorSaúde...")
        print_buscar = {
            "Especialidade": especialidade,
            "Data solicitada": buscar_data
        }

        buscando = print_caixa("Buscando horário", print_buscar)
        print(buscando)

        # ⚙️ Limpa ambiente entre chamadas
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        limite = agora + timedelta(minutes=minutos_ate_disponivel)
        data_base = datetime.strptime(data, "%d/%m/%Y") if data else agora
        print(f"🕒 Agora: {agora.strftime('%d/%m/%Y %H:%M')} — ⏳ Limite: {limite.strftime('%d/%m/%Y %H:%M')}")

        try:
            driver.get("https://amor-saude.feegow.com/pre-v7.6/?P=AgendaMultipla&Pers=1")

            if not sessao_ja_logada(driver):
                print("🔐 Sessão não ativa. Realizando login...")
                first_login = True
                fazer_login(driver, wait)
            else:
                print("🔓 Sessão já autenticada.")
                first_login = False

            for dias_adiante in range(0, 10):  # tenta pelos próximos 10 dias
                data_atual = data_base + timedelta(days=dias_adiante)
                data_str = data_atual.strftime("%d/%m/%Y")
                print(f"📆 Tentando data {data_str}...")

                if not navegar_para_data(driver, wait, data_atual, first_login):
                    print(f"❌ Não foi possível acessar a data {data_str}")
                    continue

                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-hover")))
                    print("✅ Tabela de horários apareceu.\n")
                except TimeoutException:
                    print("⛔ Tabela não apareceu após seleção. Pulando para próxima data.")
                    continue

                # Garante visibilidade da grade
                driver.execute_script("""
                                const el = document.getElementById('contQuadro');
                                if (el) {
                                    el.scrollLeft = el.scrollWidth;
                                }
                            """)

                blocos = driver.find_elements(By.CSS_SELECTOR, "td[id^='pf']")
                todos_horarios = []

                for bloco in blocos:
                    max_tentativas = 2
                    sucesso = False  # indicador se o bloco foi processado com sucesso
                    for tentativa in range(max_tentativas):
                        try:
                            medico_raw = bloco.find_element(By.CSS_SELECTOR, "div")
                            medico = medico_raw.text.strip().split("\n")[0]
                            horarios = extrair_horarios_de_bloco(bloco, especialidade)

                            for h in horarios:
                                todos_horarios.append((h, medico))
                            sucesso = True  # deu certo neste bloco
                            break  # sai do loop de tentativas para este bloco

                        except (NoSuchElementException, StaleElementReferenceException) as e:
                                # logger.warning(
                                #     f"⚠️ Erro ao acessar bloco na tentativa {tentativa + 1} ({type(e).__name__}).")
                                time.sleep(0.5)  # Pequena pausa antes da próxima tentativa

                    if not sucesso:
                        # Esse else é executado se nenhuma tentativa for bem-sucedida
                        # TODO PODE SÓ TIRAR ESSE LOG?
                        logger.warning("⚠️ Erro persistente ao acessar bloco. Pulando esse bloco.")

                if not todos_horarios:
                    print(f"⚠️ Nenhum horário na data {data_str}, tentando próxima...")
                    continue

                def converter_para_datetime(hora_str):
                    try:
                        hora_dt = datetime.strptime(hora_str, "%H:%M")
                        dt_local = datetime.combine(data_atual.date(), hora_dt.time())
                        dt_conv = dt_local.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
                        return dt_conv
                    except ValueError:
                        return None

                # horarios_validos = [
                #     # (h, m, c) for (h, m, c) in todos_horarios
                #     (h, m) for (h, m) in todos_horarios
                #     if (dt := converter_para_datetime(h)) and dt >= limite
                # ]
                # Filtra os horários válidos
                horarios_validos = []
                for (h, m) in todos_horarios:
                    dt = converter_para_datetime(h)
                    if dt is None:
                        continue

                # Se a data do agendamento for hoje, aplica o limite
                if data_atual.date() == agora.date():
                    if dt >= limite:
                        horarios_validos.append((h, m))
                        print(f"horarios validos: {horarios_validos}")
                else:
                    # Para datas futuras, não aplica o limite
                    horarios_validos.append((h, m))

                if not horarios_validos:
                    continue
                # TODO VER A COMPARAÇÃO DO ID DO SOLICITANTE
                proximos_horarios = sorted(
                    [
                        # (h, m, c) for (h, m, c) in horarios_validos
                        (h, m) for (h, m) in horarios_validos
                        if not ja_foi_enviado(solicitante_id, especialidade, data_str, h, m)
                    ],
                    key=lambda x: converter_para_datetime(x[0])
                )

                if not proximos_horarios:
                    continue

                proximo_horario, medico = proximos_horarios[0]
                registrar_agendamento(
                    usuario_id=solicitante_id,
                    especialidade=especialidade,
                    data=data_str,
                    hora=proximo_horario,
                    medico_nome=medico,
                    consultorio=""
                )

                return {
                    "data": data_str,
                    "proximo_horario": proximo_horario,
                    "medico": medico
                }

            return {
                "erro": "Nenhum horário encontrado após 10 dias."
            }


        except Exception as e:
            logger.error(f"❌ Erro inesperado: {type(e).__name__}")
            return {
                "erro": f"{type(e).__name__}"
            }


@router.post("/find_slot")
async def find_slot(body: RequisicaoHorario):
    resultado = await buscar_primeiro_horario(
        body.especialidade,
        body.solicitante_id,  # ✅ adiciona isso aqui
        body.data,
        body.minutos_ate_disponivel or 0
    )

    if isinstance(resultado, str) and resultado.lower().startswith("erro"):
        return {
            "status": "erro",
            "mensagem": resultado,
            "especialidade": body.especialidade,
            "data": body.data
        }

    if resultado is None:
        return {
            "status": "nenhum",
            "mensagem": f"Nenhum horário encontrado para {body.especialidade}.",
            "especialidade": body.especialidade,
            "data": body.data
        }

    if resultado.get("erro"):
        return {
            "status": "erro",
            "mensagem": resultado["erro"]
        }

    print_horario = {
        "Especialidade": body.especialidade,
        "Médico": resultado.get('medico'),
        "Data encontrada": resultado.get('data'),
        "Horário": resultado.get('proximo_horario')
    }

    encontrado = print_caixa("Buscando horário", print_horario)
    print(encontrado)

    return {
        "status": "ok",
        "especialidade": body.especialidade,
        "medico": resultado.get("medico"),
        "data": resultado.get("data"),
        "proximo_horario": resultado["proximo_horario"]
    }