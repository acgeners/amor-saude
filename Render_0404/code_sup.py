# 🗂 Bibliotecas
from fastapi import FastAPI
from contextlib import asynccontextmanager
import os
from pydantic import BaseModel

# 🧭 Navegador
from driver_utils import fechar_driver


@asynccontextmanager
async def lifespan(_: FastAPI):
    # inicialização opcional aqui
    yield
    if os.getenv("ENV") == "local":
        print("🛑 Encerrando driver do Selenium...")
        try:
            fechar_driver()  # ou driver.quit()
        except Exception as e:
            print(f"Erro ao encerrar o driver ({type(e).__name__})")
    else:
        print("⚠️ Ambiente de produção — mantendo driver em execução.")


class RequisicaoHorario(BaseModel):
    solicitante_id: str
    especialidade: str
    data: str | None = None
    minutos_ate_disponivel: int | None = 0

class ConfirmacaoAgendamento(BaseModel):
    matricula: str | None = None
    especialidade: str
    data: str
    hora: str
    nome_paciente: str
    CPF: str
    data_nascimento: str
    contato: str
    nome_profissional: str

class CancelarAgendamento(BaseModel):
    especialidade: str
    data: str
    hora: str
    nome_paciente: str
    nome_profissional: str


def print_caixa(titulo: str, conteudo: dict):
    lenght = len(titulo)
    bars = 40 - lenght
    bars_side = int((bars/2)-1)

    print(f"\n{'='*bars_side} {titulo.upper()} {'='*bars_side}")
    for chave, valor in conteudo.items():
        print(f"|{chave}: {valor}")
    print(f"{'=' * 40}\n")
