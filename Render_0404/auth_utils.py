# 🗂 Bibliotecas
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC # pylint: disable=invalid-name
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os


USUARIO = os.getenv("USUARIO")
SENHA = os.getenv("SENHA")


def sessao_ja_logada(driver):
    # Se o campo de login estiver visível, já sabemos que está deslogado
    if driver.find_elements(By.ID, "User"):
        return False
    # Caso contrário, confirmamos se o botão de logout está disponível
    try:
        driver.find_element(By.CSS_SELECTOR, 'a[href*="logoff"]')
        return True
    except NoSuchElementException:
        return False


def fazer_login(_driver, wait):
    try:
        input_usuario = wait.until(EC.presence_of_element_located((By.ID, "User")))
        input_senha = wait.until(EC.presence_of_element_located((By.ID, "password")))
        botao_login = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))

        input_usuario.clear()
        input_usuario.send_keys(USUARIO)
        input_senha.clear()
        input_senha.send_keys(SENHA)
        botao_login.click()
    except TimeoutException:
        print("❌ Timeout no login.")
    except Exception as e:
        print(f"❌ Erro inesperado no login: {e}")