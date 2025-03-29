from fastapi import FastAPI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# from selenium.common.exceptions import NoSuchElementException
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from typing import Union, Optional
import os
from datetime import datetime, timedelta
import asyncio
from pydantic import BaseModel
from zoneinfo import ZoneInfo


driver_lock = asyncio.Lock()
load_dotenv()

USUARIO = os.getenv("USUARIO")
SENHA = os.getenv("SENHA")
CHROME_PROFILE = os.getenv("CHROME_PROFILE_DIR", "./chrome_profile_api")

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
    especialidade: str
    data: Optional[str] = None  # formato: dd/mm/yyyy
    minutos_ate_disponivel: Optional[int] = 0  # novo parâmetro opcional

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


async def buscar_primeiro_horario(especialidade: str, data: Optional[str] = None, minutos_ate_disponivel: int = 0) -> \
Union[str, None]:
    async with driver_lock:
        import time
        import traceback
        print("🧭 Acessando AmorSaúde...")

        try:
            # ⚙️ Limpa ambiente entre chamadas
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            limite = agora + timedelta(minutes=minutos_ate_disponivel)
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
            except Exception:
                print("⚠️ Checkbox 'HVazios' não encontrada na primeira tentativa. Recarregando página...")
                driver.refresh()
                try:
                    checkbox = wait.until(EC.presence_of_element_located((By.ID, "HVazios")))
                except Exception:
                    print("❌ Checkbox ainda não apareceu. Abortando.")
                    return f"Erro ao buscar horário: filtro de horários vazios não está visível na página."

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

            # Se data não for fornecida, usa a data atual
            if not data:
                data = datetime.now().strftime("%d/%m/%Y")
                print(f"📅 Nenhuma data fornecida — usando data de hoje: {data}")
            else:
                try:
                    datetime.strptime(data, "%d/%m/%Y")
                except ValueError:
                    return f"Erro: formato de data inválido. Use dd/mm/yyyy."
            try:
                # Valida formato
                datetime.strptime(data, "%d/%m/%Y")
                print(f"📅 Buscando a data {data} no calendário...")
                wait.until(EC.presence_of_element_located((By.ID, "tblCalendario")))
                data_element = wait.until(EC.element_to_be_clickable((By.ID, data)))
                driver.execute_script("arguments[0].scrollIntoView(true);", data_element)
                data_element.click()
                time.sleep(2)
                print(f"✅ Clique na data {data} realizado com sucesso.")
            except ValueError:
                return f"Erro: formato de data inválido. Use dd/mm/yyyy."
            except Exception as e:
                print(f"⚠️ Erro ao tentar clicar na data {data}: {e}")
                return f"Erro ao clicar na data {data}: {type(e).__name__}: {str(e)}"

            blocos = driver.find_elements(By.CSS_SELECTOR, "td[id^='pf']")
            todos_horarios = []

            for bloco in blocos:
                horarios = extrair_horarios_de_bloco(bloco, especialidade)
                todos_horarios.extend(horarios)

            if todos_horarios:
                def converter_para_datetime(hora_str):
                    try:
                        hora_dt = datetime.strptime(hora_str, "%H:%M")
                        data_dt = datetime.strptime(data, "%d/%m/%Y")
                        dt_local = datetime.combine(data_dt.date(), hora_dt.time())
                        return dt_local.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))  # 👈 agora está certo
                    except ValueError:
                        return None

                # Filtra os horários que respeitam o limite mínimo
                horarios_validos = [
                    h for h in todos_horarios
                    if (dt := converter_para_datetime(h)) and dt >= limite
                ]

                if not horarios_validos:
                    print(f"⚠️ Nenhum horário válido após {limite.strftime('%H:%M')} encontrado.")
                    return None

                # Ordena e retorna o primeiro horário disponível
                horarios_validos.sort(key=converter_para_datetime)
                primeiro = horarios_validos[0]
                print(f"⏰ Primeiro horário válido encontrado: {primeiro}")
                return primeiro

            else:
                print(f"❌ Nenhum horário encontrado para {especialidade}")
                return None

        except Exception as e:
            print("❌ Erro durante a busca:")
            traceback.print_exc()
            return f"Erro ao buscar horário: {type(e).__name__}: {str(e)}"


@app.post("/n8n/horario")
async def n8n_horario(body: RequisicaoHorario):
    resultado = await buscar_primeiro_horario(
        body.especialidade,
        body.data,
        body.minutos_ate_disponivel or 0  # <- aqui agora ele vai
    )

    print(
        f"📥 especialidade={body.especialidade}, data={body.data}, minutos_ate_disponivel={body.minutos_ate_disponivel}")

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
        "data": body.data,
        "primeiro_horario": resultado
    }



# from fastapi import FastAPI, Query
# from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# # from selenium.common.exceptions import NoSuchElementException
# from dotenv import load_dotenv
# from contextlib import asynccontextmanager
# from typing import Union, Optional
# import os
# from datetime import datetime
# import asyncio
#
#
# driver_lock = asyncio.Lock()
# load_dotenv()
#
# USUARIO = os.getenv("USUARIO")
# SENHA = os.getenv("SENHA")
# CHROME_PROFILE = os.getenv("CHROME_PROFILE_DIR", "./chrome_profile_api")
#
# # 🧠 Inicializa o navegador com perfil persistente
# options = Options()
# options.add_argument(f"user-data-dir={CHROME_PROFILE}")
# options.add_argument("--disable-gpu")
# options.add_argument("--no-sandbox")
# options.add_argument("--headless=new")
# options.add_argument("--disable-dev-shm-usage")
# options.add_argument("--disable-software-rasterizer")
# options.add_argument("--disable-extensions")
# options.add_argument("--disable-infobars")
# options.add_argument("--disable-features=VizDisplayCompositor")
# options.add_argument("--remote-debugging-port=9222")
#
# # 🔒 Verifica se o perfil já está em uso
# lock_path = os.path.join(CHROME_PROFILE, "SingletonLock")
# if os.path.exists(lock_path):
#     raise RuntimeError("⚠️ Perfil do Chrome está em uso. Finalize o container anterior com 'docker-compose down'.")
#
# driver = webdriver.Chrome(options=options)
# driver.set_page_load_timeout(30)
# wait = WebDriverWait(driver, 20)
#
# @asynccontextmanager
# async def lifespan(fastapi_app: FastAPI):
#     yield
#     print(f"🛑 Encerrando driver do Selenium... App: {fastapi_app.__class__.__name__}")
#     try:
#         driver.quit()
#     except Exception as e:
#         print(f"Erro ao encerrar o driver: {e}")
#
# app = FastAPI(lifespan=lifespan)
#
# def extrair_horarios_de_bloco(bloco, especialidade: str) -> list[str]:
#     horarios = []
#
#     try:
#         painel = bloco.find_elements(By.CSS_SELECTOR, ".panel-title")
#         if not painel:
#             print("⚠️ Bloco sem .panel-title encontrado, ignorando...")
#             return []
#
#         nome_especialidade = painel[0].text.strip().lower()
#
#         linhas = nome_especialidade.split("\n")
#         nome = linhas[0] if linhas else ""
#         especialidade_prof = linhas[1] if len(linhas) > 1 else ""
#
#         print(f"🔍 Profissional detectado: {nome}")
#         print(especialidade_prof)
#
#         if especialidade.lower() in especialidade_prof:
#             # botoes = bloco.find_elements(By.CSS_SELECTOR, "button.btn-info")
#             botoes = bloco.find_elements(By.CSS_SELECTOR, ".btn-info")
#             for botao in botoes:
#                 texto = botao.text.strip()
#                 if texto:
#                     print(texto)
#                     horarios.append(texto)
#
#     except Exception as e:
#         print(f"⚠️ Erro ao processar bloco: {e}")
#
#     return horarios
#
# # def buscar_primeiro_horario(especialidade: str) -> Union[str, None]:
# # def buscar_primeiro_horario(especialidade: str, data: Optional[str] = None) -> Union[str, None]:
# async def buscar_primeiro_horario(especialidade: str, data: Optional[str] = None) -> Union[str, None]:
#     async with driver_lock:
#         import time
#         import traceback
#         print("🧭 Acessando AmorSaúde...")
#
#         try:
#             # ⚙️ Limpa ambiente entre chamadas
#             try:
#                 driver.delete_all_cookies()
#             except Exception as e:
#                 print(f"⚠️ Não foi possível limpar cookies: {e}")
#
#             try:
#                 while len(driver.window_handles) > 1:
#                     driver.switch_to.window(driver.window_handles[-1])
#                     driver.close()
#                 driver.switch_to.window(driver.window_handles[0])
#             except Exception as e:
#                 print(f"⚠️ Erro ao limpar janelas: {e}")
#
#             driver.get("https://amor-saude.feegow.com/pre-v7.6/?P=AgendaMultipla&Pers=1")
#
#             # Faz login se necessário
#             if driver.find_elements(By.ID, "User"):
#                 input_usuario = wait.until(EC.presence_of_element_located((By.ID, "User")))
#                 input_senha = wait.until(EC.presence_of_element_located((By.ID, "password")))
#
#                 input_usuario.clear()
#                 input_usuario.send_keys(USUARIO)
#                 input_senha.clear()
#                 input_senha.send_keys(SENHA)
#
#                 botao_login = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
#                 botao_login.click()
#                 print("✅ Login realizado com sucesso.")
#             else:
#                 print("🔓 Sessão já autenticada.")
#
#             # Verifica se a checkbox está visível; se não estiver, tenta recarregar a página
#             try:
#                 checkbox = wait.until(EC.presence_of_element_located((By.ID, "HVazios")))
#             except Exception:
#                 print("⚠️ Checkbox 'HVazios' não encontrada na primeira tentativa. Recarregando página...")
#                 driver.refresh()
#                 try:
#                     checkbox = wait.until(EC.presence_of_element_located((By.ID, "HVazios")))
#                 except Exception:
#                     print("❌ Checkbox ainda não apareceu. Abortando.")
#                     return f"Erro ao buscar horário: filtro de horários vazios não está visível na página."
#
#             # Força recarregamento do JS marcando e desmarcando
#             driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
#             driver.execute_script("arguments[0].click();", checkbox)
#             time.sleep(1)
#             driver.execute_script("arguments[0].click();", checkbox)
#             time.sleep(2)
#
#             # Espera a tabela aparecer
#             wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-hover")))
#             print("☑️ Filtro 'Somente horários vazios' reativado.")
#
#             # Garante visibilidade da grade
#             driver.set_window_size(1920, 1080)
#             driver.execute_script("""
#                 const el = document.getElementById('contQuadro');
#                 if (el) {
#                     el.scrollLeft = el.scrollWidth;
#                 }
#             """)
#
#             # Se data não for fornecida, usa a data atual
#             if not data:
#                 data = datetime.now().strftime("%d/%m/%Y")
#                 print(f"📅 Nenhuma data fornecida — usando data de hoje: {data}")
#             else:
#                 try:
#                     datetime.strptime(data, "%d/%m/%Y")
#                 except ValueError:
#                     return f"Erro: formato de data inválido. Use dd/mm/yyyy."
#             try:
#                 # Valida formato
#                 datetime.strptime(data, "%d/%m/%Y")
#                 print(f"📅 Buscando a data {data} no calendário...")
#                 wait.until(EC.presence_of_element_located((By.ID, "tblCalendario")))
#                 data_element = wait.until(EC.element_to_be_clickable((By.ID, data)))
#                 driver.execute_script("arguments[0].scrollIntoView(true);", data_element)
#                 data_element.click()
#                 time.sleep(2)
#                 print(f"✅ Clique na data {data} realizado com sucesso.")
#             except ValueError:
#                 return f"Erro: formato de data inválido. Use dd/mm/yyyy."
#             except Exception as e:
#                 print(f"⚠️ Erro ao tentar clicar na data {data}: {e}")
#                 return f"Erro ao clicar na data {data}: {type(e).__name__}: {str(e)}"
#
#             blocos = driver.find_elements(By.CSS_SELECTOR, "td[id^='pf']")
#             todos_horarios = []
#
#             for bloco in blocos:
#                 horarios = extrair_horarios_de_bloco(bloco, especialidade)
#                 todos_horarios.extend(horarios)
#
#             if todos_horarios:
#                 def converter_para_minutos(hora_str):
#                     try:
#                         h, m = map(int, hora_str.split(":"))
#                         return h * 60 + m
#                     except ValueError:
#                         return float('inf')
#
#                 todos_horarios.sort(key=converter_para_minutos)
#                 primeiro = todos_horarios[0]
#                 print(f"⏰ Primeiro horário encontrado: {primeiro}")
#                 return primeiro
#
#             else:
#                 print(f"❌ Nenhum horário encontrado para {especialidade}")
#                 return None
#
#         except Exception as e:
#             print("❌ Erro durante a busca:")
#             traceback.print_exc()
#             return f"Erro ao buscar horário: {type(e).__name__}: {str(e)}"
#
# @app.get("/horario")
# # def get_horario(especialidade: str = Query(..., description="Nome da especialidade")):
# # def get_horario(
# #     especialidade: str = Query(..., description="Nome da especialidade"),
# #     data: Optional[str] = Query(None, description="Data no formato dd/mm/yyyy (opcional)")
# # ):
# @app.get("/horario")
# async def get_horario(
#     especialidade: str = Query(..., description="Nome da especialidade"),
#     data: Optional[str] = Query(None, description="Data no formato dd/mm/yyyy (opcional)")
# ):
#     print(f"\n\n📥 Requisição recebida: especialidade = {especialidade}, data = {data}")
#     resultado = await buscar_primeiro_horario(especialidade, data)
#
#     if isinstance(resultado, str) and resultado.lower().startswith("erro"):
#         print(f"📤 Retorno: {{'erro': '{resultado}'}}")
#         return {"erro": resultado}
#
#     elif resultado is None:
#         print(f"📤 Retorno: {{'mensagem': 'Nenhum horário encontrado para {especialidade}'}}")
#         return {"mensagem": f"Nenhum horário encontrado para {especialidade}"}
#
#     else:
#         print(f"📤 Retorno: {{'especialidade': '{especialidade}', 'primeiro_horario': '{resultado}'}}")
#         return {
#             "especialidade": especialidade,
#             "primeiro_horario": resultado
#         }
#
