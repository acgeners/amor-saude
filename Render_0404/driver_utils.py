# 🗂 Bibliotecas
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.chrome.service import Service
import os
import asyncio
import logging


# 📉 Reduz o nível de log da biblioteca selenium
logging.getLogger("selenium").setLevel(logging.WARNING)

_driver: WebDriver | None = None
driver_lock = asyncio.Lock()

# Obtém o diretório do perfil do Chrome a partir da variável CHROME_PROFILE_DIR
CHROME_PROFILE = os.getenv("CHROME_PROFILE_DIR", "./chrome_profile_api")


# 🧠 Inicializa o navegador com perfil persistente
def get_driver():
    global _driver
    if _driver is None:
        # Obtém a URL remota do Selenium, se definida
        remote_url = os.getenv("SELENIUM_REMOTE_URL") or False

        # Se estivermos em ambiente local e NÃO utilizando Selenium remoto, verifica o bloqueio do perfil
        if os.getenv("ENV") == "local" and not remote_url:
            lock_path = os.path.join(CHROME_PROFILE, "SingletonLock")
            if os.path.exists(lock_path):
                raise RuntimeError("⚠️ Perfil do Chrome está em uso. Finalize o container anterior.")

        options = Options()
        # Só adiciona o user-data-dir se NÃO estivermos usando o driver remoto
        if not remote_url:
            options.add_argument(f"user-data-dir={CHROME_PROFILE}")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        # Ativa o modo headless quando NÃO estiver em ambiente local (ou seja, quando rodando via API/Render)
        if os.getenv("ENV") != "local":
            options.add_argument("--headless=new")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--log-level=3")
        options.add_argument("--silent")

        if remote_url:
            # Conecta ao Selenium remoto (por exemplo, container Selenium)
            _driver = webdriver.Remote(
                command_executor=remote_url,
                options=options
            )
        else:
            # Caso contrário, utiliza o driver local (Chrome instalado no container)
            service = Service(log_path=os.devnull)
            _driver = webdriver.Chrome(service=service, options=options)

        _driver.set_window_size(1920, 1080)
        _driver.set_page_load_timeout(30)
    return _driver


def fechar_driver():
    global _driver
    if _driver:
        _driver.quit()
        _driver = None


def extrair_cookies_selenium(driver) -> dict:
    """
    Extrai os cookies do navegador do Selenium e converte para dict do requests.
    """
    selenium_cookies = driver.get_cookies()
    return {cookie['name']: cookie['value'] for cookie in selenium_cookies}


def garantir_aba_principal(driver):
    try:
        while len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            driver.close()
        driver.switch_to.window(driver.window_handles[0])
    except Exception as e:
        print(f"⚠️ Erro ao garantir aba principal: {e}")