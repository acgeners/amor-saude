# 🗂 Bibliotecas
from fastapi import APIRouter
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from typing import Union, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from selenium.webdriver.support.wait import WebDriverWait
import traceback

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
from booking import extrair_consultorio_do_bloco


router = APIRouter()


async def buscar_primeiro_horario(especialidade: str, solicitante_id: str, data: Optional[str] = None,
                                  minutos_ate_disponivel: int = 0) -> Union[dict[str, str], None]:
    async with driver_lock:
        driver = get_driver()
        wait = WebDriverWait(driver, 20)
        # TODO só se der problema nas abas
        # garantir_aba_principal(driver)  # 🧠 Garante que estamos na aba certa

        print("🧭 Acessando AmorSaúde...")

        # ⚙️ Limpa ambiente entre chamadas
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        limite = agora + timedelta(minutes=minutos_ate_disponivel)
        data_base = datetime.strptime(data, "%d/%m/%Y") if data else agora
        print(f"🕒 Agora: {agora.strftime('%d/%m/%Y %H:%M')} — ⏳ Limite: {limite.strftime('%d/%m/%Y %H:%M')}")

        try:
            driver.get("https://amor-saude.feegow.com/pre-v7.6/?P=AgendaMultipla&Pers=1")

            if not sessao_ja_logada(driver):
                print("🔐 Sessão não ativa. Realizando login...")
                fazer_login(driver, wait)
            else:
                print("🔓 Sessão já autenticada.")

            for dias_adiante in range(0, 30):  # tenta pelos próximos 30 dias
                data_atual = data_base + timedelta(days=dias_adiante)
                data_str = data_atual.strftime("%d/%m/%Y")
                print(f"📆 Tentando data {data_str}...")

                if not navegar_para_data(driver, wait, data_atual):
                    print(f"❌ Não foi possível acessar a data {data_str}")
                    continue

                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-hover")))
                    print("✅ Tabela de horários apareceu.")
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
                    try:
                        medico_raw = bloco.find_element(By.CSS_SELECTOR, "div")
                        medico = medico_raw.text.strip().split("\n")[0]
                        horarios = extrair_horarios_de_bloco(bloco, especialidade)

                        try:
                            consultorio = extrair_consultorio_do_bloco(bloco)
                        except Exception as e:
                            print(f"ℹ️ Consultório não encontrado: {e}. Usando valor None.")
                            consultorio = None  # ou "Desconhecido", "", etc.

                        for h in horarios:
                            todos_horarios.append((h, medico, consultorio))
                    except (NoSuchElementException, StaleElementReferenceException) as e:
                        print(f"⚠️ Erro ao acessar bloco: {e}. Pulando esse bloco.")
                        continue

                if not todos_horarios:
                    print(f"⚠️ Nenhum horário na data {data_str}, tentando próxima...")
                    continue

                def converter_para_datetime(hora_str):
                    try:
                        hora_dt = datetime.strptime(hora_str, "%H:%M")
                        dt_local = datetime.combine(data_atual.date(), hora_dt.time())
                        return dt_local.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
                    except ValueError:
                        return None

                horarios_validos = [
                    (h, m, c) for (h, m, c) in todos_horarios
                    if (dt := converter_para_datetime(h)) and dt >= limite
                ]

                if not horarios_validos:
                    continue

                proximos_horarios = sorted(
                    [
                        (h, m, c) for (h, m, c) in horarios_validos
                        if not ja_foi_enviado(solicitante_id, especialidade, data_str, h, m)
                    ],
                    key=lambda x: converter_para_datetime(x[0])
                )

                if not proximos_horarios:
                    continue

                proximo_horario, medico, consultorio = proximos_horarios[0]
                registrar_agendamento(
                    usuario_id=solicitante_id,
                    especialidade=especialidade,
                    data=data_str,
                    hora=proximo_horario,
                    medico_nome=medico,
                    consultorio=consultorio
                )

                return {
                    "data": data_str,
                    "proximo_horario": proximo_horario,
                    "medico": medico,
                    "consultorio": consultorio
                }

            return {
                "erro": "Nenhum horário encontrado após 30 dias."
            }

        except Exception as e:
            traceback.print_exc()
            return {
                "erro": f"{type(e).__name__}: {str(e)}"
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

    return {
        "status": "ok",
        "especialidade": body.especialidade,
        "medico": resultado.get("medico"),
        # "consultorio": resultado.get("consultorio"), TODO verificar se inclui isso
        "data": resultado.get("data"),
        "proximo_horario": resultado["proximo_horario"]
    }