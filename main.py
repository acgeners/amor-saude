# 🗂 Bibliotecas
import os
from fastapi import FastAPI
from dotenv import load_dotenv
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import logging

# 🧭 Rotas
from find_slot import router as slot_finder
from make_appointment import router as appointment_maker

# 📑 Modelos e lifespan
from code_sup import lifespan


logging.basicConfig(level=logging.WARNING)
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

print("API pronta pra receber request")

middleware = [
    Middleware(
        CORSMiddleware, # type: ignore
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

app = FastAPI(
    title="Amor Saúde API",
    version="1.0.0",
    description="Consulta de disponibilidade e agendamento de horários",
    lifespan=lifespan,
    middleware=middleware
)


# Registrando as rotas
app.include_router(slot_finder, prefix="/amor-saude")
app.include_router(appointment_maker, prefix="/amor-saude")

@app.get("/ping")
async def ping():
    return {"status": "ok"}


