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

CHROME_PROFILE = os.getenv("CHROME_PROFILE_DIR", "./chrome_profile_api")


# 🧠 Inicializa o navegador com perfil persistente
def get_driver():
    global _driver
    if _driver is None:
        # 🔒 Verifica se o perfil já está em uso
        if os.getenv("ENV") == "local":
            lock_path = os.path.join(CHROME_PROFILE, "SingletonLock")
            if os.path.exists(lock_path):
                raise RuntimeError("⚠️ Perfil do Chrome está em uso. Finalize o container anterior.")

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
        options.add_argument("--log-level=3")  # Silencia logs do Chrome
        options.add_argument("--silent")  # Silencia ainda mais logs

        # 🔇 Silencia logs do ChromeDriver
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