# 🗂 Bibliotecas
from fastapi import FastAPI
from contextlib import asynccontextmanager
import os
from pydantic import BaseModel

# 🧭 Navegador
from driver_utils_continuar import fechar_driver


@asynccontextmanager
async def lifespan(_: FastAPI):
    # inicialização opcional aqui
    yield
    if os.getenv("ENV") == "local":
        print("🛑 Encerrando driver do Selenium...")
        try:
            fechar_driver()  # ou driver.quit()
        except Exception as e:
            print(f"Erro ao encerrar o driver: {e}")
    else:
        print("⚠️ Ambiente de produção — mantendo driver em execução.")


class RequisicaoHorario(BaseModel):
    solicitante_id: str
    especialidade: str
    data: str | None = None
    minutos_ate_disponivel: int | None = 0

class ConfirmacaoAgendamento(BaseModel):
    solicitante_id: str
    especialidade: str
    data: str
    hora: str
    nome_paciente: str
    CPF: str
    data_nascimento: str
    contato: str
    nome_profissional: str

# class RequisicaoHorario(BaseModel):
#     solicitante_id: str  # novo campo obrigatório
#     especialidade: str
#     data: Optional[str] = None
#     minutos_ate_disponivel: Optional[int] = 0