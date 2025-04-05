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
            "Paciente ID": solicitante_id,
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

                disp = True
                if not navegar_para_data(driver, wait, data_atual, first_login, disp):
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
                time.sleep(1)
                blocos = driver.find_elements(By.CSS_SELECTOR, "td[id^='pf']")
                todos_horarios = []

                for bloco in blocos:
                    max_tentativas = 2
                    sucesso = False  # indicador se o bloco foi processado com sucesso
                    for tentativa in range(max_tentativas):
                        try:
                            # Reobtém o bloco específico dentro da lista atual de blocos
                            blocos = driver.find_elements(By.CSS_SELECTOR, "td[id^='pf']")
                            # Verifica se o índice do bloco atual ainda é válido
                            index = blocos.index(bloco) if bloco in blocos else None
                            if index is None:
                                print(f"❌ Bloco '{bloco.text}' não está mais disponível. Ignorando.")
                                break  # Sai do loop interno para começar outro bloco

                            bloco = blocos[index]  # Reassocia ao bloco válido

                            # Processa o bloco normalmente
                            medico_raw = bloco.find_element(By.CSS_SELECTOR, "div")
                            medico = medico_raw.text.strip().split("\n")[0]
                            horarios = extrair_horarios_de_bloco(bloco, especialidade)

                            if horarios:  # Apenas adiciona se houver horários encontrados
                                for h in horarios:
                                    todos_horarios.append((h, medico))

                            # print(f"Todos os horários: {todos_horarios}")
                            sucesso = True  # deu certo neste bloco
                            break  # sai do loop de tentativas para este bloco

                        except (NoSuchElementException, StaleElementReferenceException):
                                # TODO tirei o 'as e:', ver se deu erro
                                # logger.warning(
                                #     f"⚠️ Erro ao acessar bloco na tentativa {tentativa + 1} ({type(e).__name__}).")
                                time.sleep(0.5)  # Pequena pausa antes da próxima tentativa

                    if not sucesso:
                        # Esse else é executado se nenhuma tentativa for bem-sucedida
                        # TODO VERIFICAR SE DEU CERTO A MUDANÇA
                        # logger.warning("⚠️ Erro persistente ao acessar bloco. Pulando esse bloco.")
                        pass

                if not todos_horarios:
                    print(f"⚠️ Nenhum horário na data {data_str}, tentando próxima...")
                    continue

                def converter_para_datetime(hora_str):
                    try:
                        hora_dt = datetime.strptime(hora_str, "%H:%M")
                        dt_local = datetime.combine(data_atual.date(), hora_dt.time())
                        dt_conv = dt_local.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
                        return dt_conv
                    except ValueError as e2:
                        print(f"Erro ao converter '{hora_str}' para datetime: {e2}")
                        return None

                # Filtra os horários válidos
                horarios_validos = []
                for (h, m) in todos_horarios:
                    # print(f"Testando horário: {h}, Médico: {m}")
                    dt = converter_para_datetime(h)
                    if dt is None:
                        continue

                    # Se a data do agendamento for hoje, aplica o limite
                    if data_atual.date() == agora.date():
                        # print("É data atual")
                        if dt >= limite:
                            # print("Horário é depois do limite minimo")
                            horarios_validos.append((h, m))
                    else:
                        # Para datas futuras, não aplica o limite
                        # print("Data desejada não é hoje")
                        horarios_validos.append((h, m))

                    # print(f"horarios validos 1: {horarios_validos}")


                if not horarios_validos:
                    logger.info(f"⚠️ Nenhum horário válido encontrado em {data_str}. Tentando próxima data...")
                    continue

                # print(f"horarios validos 2: {horarios_validos}")

                proximos_horarios = sorted(
                    [
                        # (h, m) para cada horário válido em horarios_validos
                        (h, m) for (h, m) in horarios_validos
                        if not ja_foi_enviado(solicitante_id, especialidade, data_str, h, m)
                    ],
                    key=lambda x: converter_para_datetime(x[0])
                )

                # Adicionando logs
                logger.info("Iniciando filtragem dos horários válidos.")
                for h, m in horarios_validos:
                    if not ja_foi_enviado(solicitante_id, especialidade, data_str, h, m):
                        logger.debug(f"Horário válido encontrado: {h}:{m}")
                    else:
                        logger.debug(f"Horário DESCONSIDERADO (já enviado): {h}:{m}")

                logger.info(
                    f"Horários filtrados: {[(h, m) for (h, m) in horarios_validos if not ja_foi_enviado(solicitante_id, especialidade, data_str, h, m)]}")

                # Após a ordenação
                logger.info("Horários filtrados e ordenados com sucesso.")

                if not proximos_horarios:
                    continue
                print(f"proximos horarios: {proximos_horarios}")
                proximo_horario, medico = proximos_horarios[0]
                registrar_agendamento(
                    usuario_id=solicitante_id,
                    especialidade=especialidade,
                    data=data_str,
                    hora=proximo_horario,
                    medico_nome=medico,
                    consultorio=""
                )
                print("Registrou o agendamento")
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

    encontrado = print_caixa("Horário encontrado", print_horario)
    print(encontrado)

    return {
        "status": "ok",
        "especialidade": body.especialidade,
        "medico": resultado.get("medico"),
        "data": resultado.get("data"),
        "proximo_horario": resultado["proximo_horario"]
    }