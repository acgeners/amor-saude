# 🗂 Bibliotecas
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from datetime import datetime
import time


abreviacoes_meses = {
    1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR", 5: "MAI", 6: "JUN",
    7: "JUL", 8: "AGO", 9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ"
}


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

        print(f"🔍 Profissional detectado: {nome} / {especialidade_prof}")
        # print(especialidade_prof)

        if especialidade.lower() in especialidade_prof:
            botoes = bloco.find_elements(By.CSS_SELECTOR, ".btn-info")
            for botao in botoes:
                try:
                    texto = botao.text.strip()
                    if texto:
                        print(texto)
                        horarios.append(texto)
                except Exception as e:
                    print(f"⚠️ Botão obsoleto ignorado ({type(e).__name__})")

    except Exception as e:
        print(f"⚠️ Erro ao processar bloco ({type(e).__name__})")

    return horarios


def navegar_para_data(driver, wait, target_date: datetime, first) -> bool:
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
                        print(f"📌 Data {id_data} clicada com sucesso.")
                        time.sleep(1.5)

                        # ✅ Depois do clique na data: marca/desmarca checkbox
                        if first:
                            time.sleep(1.5)
                        try:
                            checkbox = wait.until(EC.presence_of_element_located((By.ID, "HVazios")))
                            driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                            driver.execute_script("arguments[0].click();", checkbox)
                            time.sleep(1)
                            # Verifica se o checkbox já está selecionado
                            if checkbox.is_selected():
                                print("✅ Checkbox 'Somente horários vazios' já está marcado.")
                            else:
                                # Se não estiver marcado, clica no checkbox para marcá-lo
                                driver.execute_script("arguments[0].click();", checkbox)
                                time.sleep(1)  # Pequena espera para garantir que o clique foi processado
                                print("☑️ Checkbox 'Somente horários vazios' foi marcada.")

                        except TimeoutException:
                            print("⚠️ Checkbox não encontrada após clicar na data.")
                            return False

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
