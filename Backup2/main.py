from fastapi import FastAPI, Query
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
from typing import Union
import os
import time
import traceback

import tempfile
import shutil


load_dotenv()

USUARIO = os.getenv("USUARIO")
SENHA = os.getenv("SENHA")

app = FastAPI()

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
            botoes = bloco.find_elements(By.CSS_SELECTOR, "button.btn-info")
            for botao in botoes:
                texto = botao.text.strip()
                if texto:
                    print(texto)
                    horarios.append(texto)

    except Exception as e:
        print(f"⚠️ Erro ao processar bloco: {e}")

    return horarios

def buscar_primeiro_horario(especialidade: str) -> Union[str, None]:
    print("🧭 Acessando AmorSaúde...")

    # Cria diretório temporário isolado para esta requisição
    temp_profile_dir = tempfile.mkdtemp()
    print(f"🧪 Perfil temporário criado em: {temp_profile_dir}")

    options = Options()
    options.add_argument(f"user-data-dir={temp_profile_dir}")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--remote-debugging-port=9222")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    wait = WebDriverWait(driver, 20)

    try:
        driver.get("https://amor-saude.feegow.com/pre-v7.6/?P=AgendaMultipla&Pers=1")

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

        checkbox_candidates = driver.find_elements(By.ID, "HVazios")
        if not checkbox_candidates:
            print("⚠️ Checkbox 'HVazios' não encontrada na primeira tentativa. Recarregando página...")
            driver.refresh()
            time.sleep(2)
            checkbox_candidates = driver.find_elements(By.ID, "HVazios")

        if not checkbox_candidates:
            print("❌ Checkbox ainda não apareceu. Abortando.")
            return f"Erro ao buscar horário: filtro de horários vazios não está visível na página."

        checkbox = checkbox_candidates[0]

        driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
        driver.execute_script("arguments[0].click();", checkbox)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", checkbox)
        time.sleep(2)

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-hover")))
        print("☑️ Filtro 'Somente horários vazios' reativado.")

        driver.set_window_size(1920, 1080)
        driver.execute_script("""
            const el = document.getElementById('contQuadro');
            if (el) {
                el.scrollLeft = el.scrollWidth;
            }
        """)

        blocos = driver.find_elements(By.CSS_SELECTOR, "td[id^='pf']")
        todos_horarios = []

        for bloco in blocos:
            horarios = extrair_horarios_de_bloco(bloco, especialidade)
            todos_horarios.extend(horarios)

        if todos_horarios:
            def converter_para_minutos(hora_str):
                try:
                    h, m = map(int, hora_str.split(":"))
                    return h * 60 + m
                except ValueError:
                    return float('inf')

            todos_horarios.sort(key=converter_para_minutos)
            primeiro = todos_horarios[0]
            print(f"⏰ Primeiro horário encontrado: {primeiro}")
            return primeiro
        else:
            print(f"❌ Nenhum horário encontrado para {especialidade}")
            return None

    except Exception as e:
        print("❌ Erro durante a busca:")
        traceback.print_exc()
        return f"Erro ao buscar horário: {type(e).__name__}: {str(e)}"

    finally:
        try:
            driver.quit()
            shutil.rmtree(temp_profile_dir)
            print(f"🧼 Perfil temporário removido: {temp_profile_dir}")
        except Exception as e:
            print(f"⚠️ Erro ao encerrar ou limpar: {e}")

@app.get("/horario")
def get_horario(especialidade: str = Query(..., description="Nome da especialidade")):
    print(f"\n\n📥 Requisição recebida: especialidade = {especialidade}")
    resultado = buscar_primeiro_horario(especialidade)

    if isinstance(resultado, str) and resultado.lower().startswith("erro"):
        print(f"📤 Retorno: {{'erro': '{resultado}'}}")
        return {"erro": resultado}

    elif resultado is None:
        print(f"📤 Retorno: {{'mensagem': 'Nenhum horário encontrado para {especialidade}'}}")
        return {"mensagem": f"Nenhum horário encontrado para {especialidade}"}

    else:
        print(f"📤 Retorno: {{'especialidade': '{especialidade}', 'primeiro_horario': '{resultado}'}}")
        return {
            "especialidade": especialidade,
            "primeiro_horario": resultado
        }
