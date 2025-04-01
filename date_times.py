# 🗂 Bibliotecas
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from typing import Union, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from selenium.webdriver.support.wait import WebDriverWait
import time
import traceback


# 🧭 Navegador
from driver_utils import get_driver, driver_lock

# 🔐 Sessão e login
from auth_utils import sessao_ja_logada, fazer_login

# 💾 Redis
from redis_utils import registrar_agendamento, ja_foi_enviado

# 📅 Agendamento
from booking import extrair_consultorio_do_bloco


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

        print(f"🔍 Profissional detectado: {nome}")
        print(especialidade_prof)

        if especialidade.lower() in especialidade_prof:
            botoes = bloco.find_elements(By.CSS_SELECTOR, ".btn-info")
            for botao in botoes:
                try:
                    texto = botao.text.strip()
                    if texto:
                        print(texto)
                        horarios.append(texto)
                except Exception as e:
                    print(f"⚠️ Botão obsoleto ignorado: {e}")

    except Exception as e:
        print(f"⚠️ Erro ao processar bloco: {e}")

    return horarios


def navegar_para_data(driver, wait, target_date: datetime) -> bool:
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
                        try:
                            checkbox = wait.until(EC.presence_of_element_located((By.ID, "HVazios")))
                            driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                            driver.execute_script("arguments[0].click();", checkbox)
                            time.sleep(1)
                            driver.execute_script("arguments[0].click();", checkbox)
                            time.sleep(2)
                            print("☑️ Checkbox 'Somente horários vazios' marcada/desmarcada.")
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
                        consultorio = extrair_consultorio_do_bloco(bloco)

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
                        if not ja_foi_enviado(solicitante_id, especialidade, data_str, h)
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