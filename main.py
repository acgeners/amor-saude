import json
from fastapi import FastAPI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from typing import Union, Optional
import os
from datetime import datetime, timedelta
import asyncio
from pydantic import BaseModel
from zoneinfo import ZoneInfo
import time
import traceback
import redis

driver_lock = asyncio.Lock()
historico_horarios = {}  # (solicitante_id, especialidade, data) -> [horários já retornados]
load_dotenv()

USUARIO = os.getenv("USUARIO")
SENHA = os.getenv("SENHA")
CHROME_PROFILE = os.getenv("CHROME_PROFILE_DIR", "./chrome_profile_api")
REDIS_URL = os.getenv("REDIS_URL")
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

abreviacoes_meses = {
    1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR", 5: "MAI", 6: "JUN",
    7: "JUL", 8: "AGO", 9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ"
}

# 🧠 Inicializa o navegador com perfil persistente
options = Options()
options.add_argument(f"user-data-dir={CHROME_PROFILE}")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--headless=new")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-software-rasterizer")
options.add_argument("--disable-extensions")
options.add_argument("--disable-infobars")
options.add_argument("--disable-features=VizDisplayCompositor")
options.add_argument("--remote-debugging-port=9222")

# 🔒 Verifica se o perfil já está em uso
lock_path = os.path.join(CHROME_PROFILE, "SingletonLock")
if os.path.exists(lock_path):
    raise RuntimeError("⚠️ Perfil do Chrome está em uso. Finalize o container anterior com 'docker-compose down'.")

driver = webdriver.Chrome(options=options)
driver.set_page_load_timeout(30)
wait = WebDriverWait(driver, 20)

class RequisicaoHorario(BaseModel):
    solicitante_id: str  # novo campo obrigatório
    especialidade: str
    data: Optional[str] = None
    minutos_ate_disponivel: Optional[int] = 0

# def marcar_horario_como_enviado(solicitante_id, especialidade, data, horario):
#     chave = f"{solicitante_id}:{especialidade.lower()}:{data}"
#     historico: Optional[str] = redis_client.get(chave)
#     lista = json.loads(historico) if historico else []
#
#     if horario not in lista:
#         lista.append(horario)
#
#         # ⏱ Define o tempo de expiração como 24 horas (em segundos)
#         redis_client.setex(chave, 86400, json.dumps(lista))  # 86400s = 24h

def marcar_horario_como_enviado(solicitante_id, especialidade, data, horario):
    chave = f"{solicitante_id}:{especialidade.lower()}:{data}"
    historico: Optional[str] = redis_client.get(chave)
    lista = json.loads(historico) if historico else []

    if horario not in lista:
        lista.append(horario)

        # ⏳ Calcula quantos segundos faltam até o fim do dia (23:59:59)
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        fim_do_dia = datetime(agora.year, agora.month, agora.day, 23, 59, 59, tzinfo=ZoneInfo("America/Sao_Paulo"))
        segundos_ate_fim_do_dia = int((fim_do_dia - agora).total_seconds())

        redis_client.setex(chave, segundos_ate_fim_do_dia, json.dumps(lista))


def ja_foi_enviado(solicitante_id, especialidade, data, horario):
    chave = f"{solicitante_id}:{especialidade.lower()}:{data}"
    historico: Optional[str] = redis_client.get(chave)
    if not historico:
        return False
    return horario in json.loads(historico)

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    yield
    print(f"🛑 Encerrando driver do Selenium... App: {fastapi_app.__class__.__name__}")
    try:
        driver.quit()
    except Exception as e:
        print(f"Erro ao encerrar o driver: {e}")

app = FastAPI(lifespan=lifespan)

def extrair_horarios_de_bloco(bloco, especialidade: str) -> list[str]:
    horarios = []

    try:
        painel = bloco.find_elements(By.CSS_SELECTOR, ".panel-title")
        if not painel:
            print("⚠️ Bloco sem .panel-title encontrado, ignorando...")
            return []

        nome_especialidade = painel[0].text.strip().lower()

        linhas = nome_especialidade.split("\n")
        nome = linhas[0] if linhas else ""
        especialidade_prof = linhas[1] if len(linhas) > 1 else ""

        print(f"🔍 Profissional detectado: {nome}")
        print(especialidade_prof)

        if especialidade.lower() in especialidade_prof:
            # botoes = bloco.find_elements(By.CSS_SELECTOR, "button.btn-info")
            botoes = bloco.find_elements(By.CSS_SELECTOR, ".btn-info")
            for botao in botoes:
                texto = botao.text.strip()
                if texto:
                    print(texto)
                    horarios.append(texto)

    except Exception as e:
        print(f"⚠️ Erro ao processar bloco: {e}")

    return horarios


async def buscar_primeiro_horario(especialidade: str, solicitante_id: str, data: Optional[str] = None,
                                  minutos_ate_disponivel: int = 0) -> Union[dict[str, str], None]:
    async with driver_lock:
        print("🧭 Acessando AmorSaúde...")

        def navegar_para_data(target_date: datetime) -> bool:
            try:
                wait.until(EC.presence_of_element_located((By.ID, "tblCalendario")))

                for _ in range(12):  # tenta no máximo 12 meses à frente
                    # Lê o mês atual exibido no calendário
                    try:
                        ths = driver.find_elements(By.CSS_SELECTOR, "#tblCalendario th")
                        mes_atual_th = next((th for th in ths if " - " in th.text), None)
                        if not mes_atual_th:
                            print("⚠️ Não foi possível identificar o mês atual do calendário.")
                            return False

                        mes_atual_texto = mes_atual_th.text.strip().upper()  # ex: 'MAR - 2025'
                        mes_desejado_texto = f"{abreviacoes_meses[target_date.month]} - {target_date.year}"

                        if mes_atual_texto == mes_desejado_texto:
                            id_data = target_date.strftime("%d/%m/%Y")
                            # Agora tenta clicar na célula da data desejada
                            try:
                                data_element = wait.until(EC.element_to_be_clickable((By.ID, id_data)))
                                driver.execute_script("arguments[0].scrollIntoView(true);", data_element)
                                data_element.click()
                                time.sleep(1.5)
                                return True
                            except Exception as e_data:
                                print(f"⚠️ Falha ao clicar na data {id_data}: {e_data}")
                                return False
                        else:
                            # Mês ainda não é o certo: avança
                            botoes_direita = driver.find_elements(By.CSS_SELECTOR,
                                                                  "table#tblCalendario th.hand.text-right")
                            for botao in botoes_direita:
                                if botao.get_attribute("onclick") and "changeMonth" in botao.get_attribute("onclick"):
                                    driver.execute_script("arguments[0].click();", botao)
                                    time.sleep(1.5)
                                    break
                            else:
                                print("⚠️ Botão de próximo mês não encontrado.")
                                return False

                    except Exception as e_mes:
                        print(f"⚠️ Erro ao comparar/avançar mês: {e_mes}")
                        return False

            except Exception as e_data2:
                print(f"⚠️ Erro geral ao navegar até a data {target_date.strftime('%d/%m/%Y')}: {e_data2}")
            return False

        try:
            # ⚙️ Limpa ambiente entre chamadas
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            limite = agora + timedelta(minutes=minutos_ate_disponivel)
            data_base = datetime.strptime(data, "%d/%m/%Y") if data else agora
            print(f"🕒 Agora: {agora.strftime('%d/%m/%Y %H:%M')} — ⏳ Limite: {limite.strftime('%d/%m/%Y %H:%M')}")

            try:
                driver.delete_all_cookies()
            except Exception as e:
                print(f"⚠️ Não foi possível limpar cookies: {e}")

            try:
                while len(driver.window_handles) > 1:
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.close()
                driver.switch_to.window(driver.window_handles[0])
            except Exception as e:
                print(f"⚠️ Erro ao limpar janelas: {e}")

            driver.get("https://amor-saude.feegow.com/pre-v7.6/?P=AgendaMultipla&Pers=1")

            # Faz login se necessário
            if driver.find_elements(By.ID, "User"):
                input_usuario = wait.until(EC.presence_of_element_located((By.ID, "User")))
                input_senha = wait.until(EC.presence_of_element_located((By.ID, "password")))

                input_usuario.clear()
                input_usuario.send_keys(USUARIO)
                input_senha.clear()
                input_senha.send_keys(SENHA)

                botao_login = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
                botao_login.click()
                print("✅ Login realizado com sucesso.")
            else:
                print("🔓 Sessão já autenticada.")

            # Verifica se a checkbox está visível; se não estiver, tenta recarregar a página
            try:
                checkbox = wait.until(EC.presence_of_element_located((By.ID, "HVazios")))
            except TimeoutException:
                print("⚠️ Checkbox 'HVazios' não encontrada na primeira tentativa. Recarregando página...")
                driver.refresh()
                try:
                    checkbox = wait.until(EC.presence_of_element_located((By.ID, "HVazios")))
                except TimeoutException:
                    print("❌ Checkbox ainda não apareceu. Abortando.")
                    return {
                        "erro": f"{type(e).__name__}: {str(e)}"
                    }

            # Força recarregamento do JS marcando e desmarcando
            driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
            driver.execute_script("arguments[0].click();", checkbox)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", checkbox)
            time.sleep(2)

            # Espera a tabela aparecer
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-hover")))
            print("☑️ Filtro 'Somente horários vazios' reativado.")

            # Garante visibilidade da grade
            driver.set_window_size(1920, 1080)
            driver.execute_script("""
                const el = document.getElementById('contQuadro');
                if (el) {
                    el.scrollLeft = el.scrollWidth;
                }
            """)

            for dias_adiante in range(0, 30):  # tenta pelos próximos 30 dias
                data_atual = data_base + timedelta(days=dias_adiante)
                data_str = data_atual.strftime("%d/%m/%Y")
                print(f"📆 Tentando data {data_str}...")

                sucesso = navegar_para_data(data_atual)
                if not sucesso:
                    print(f"❌ Não foi possível acessar a data {data_str}")
                    continue

                blocos = driver.find_elements(By.CSS_SELECTOR, "td[id^='pf']")
                todos_horarios = []

                for bloco in blocos:
                    horarios = extrair_horarios_de_bloco(bloco, especialidade)
                    todos_horarios.extend(horarios)

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
                    h for h in todos_horarios
                    if (dt := converter_para_datetime(h)) and dt >= limite
                ]

                if not horarios_validos:
                    continue

                proximos_horarios = [
                    h for h in horarios_validos
                    if not ja_foi_enviado(solicitante_id, especialidade, data_str, h)
                ]

                if not proximos_horarios:
                    continue

                proximo_horario = proximos_horarios[0]
                marcar_horario_como_enviado(solicitante_id, especialidade, data_str, proximo_horario)

                return {
                    "data": data_str,
                    "proximo_horario": proximo_horario
                }

            return None  # nenhum horário encontrado após 30 dias

        except Exception as e:
            traceback.print_exc()
            return {
                "erro": f"{type(e).__name__}: {str(e)}"
            }


@app.post("/n8n/horario")
async def n8n_horario(body: RequisicaoHorario):
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

    return {
        "status": "ok",
        "especialidade": body.especialidade,
        "data": resultado["data"],
        "proximo_horario": resultado["proximo_horario"]
    }
