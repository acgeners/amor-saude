# 🗂 Bibliotecas
import json
import os
import unicodedata
import re
from redis import from_url
from datetime import datetime


REDIS_URL = os.getenv("REDIS_URL")
redis_client = from_url(REDIS_URL, decode_responses=True)


def normalizar_nome(nome: str) -> str:
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome).encode('ascii', 'ignore').decode('utf-8')
    nome = re.sub(r'\s+', '_', nome)  # substitui espaços por _
    return nome


def registrar_agendamento(usuario_id: str, especialidade: str, data: str, hora: str, medico_nome: str, consultorio: str, ttl: int = 86400):
    nome_normalizado = normalizar_nome(medico_nome)
    chave = f"agendamento:{usuario_id}:{especialidade.lower()}:{data}:{hora}:{nome_normalizado}"

    dados = {
        "especialidade": especialidade,
        "data": data,
        "hora": hora,
        "usuario_id": usuario_id,
        "medico_nome": medico_nome,
        "consultorio": consultorio,
        "registrado_em": datetime.now().isoformat()
    }

    # ⏱ Define o tempo de expiração como 24 horas (em segundos)
    redis_client.setex(chave, ttl, json.dumps(dados))
    print(f"\n💾 Horário disponível armazenado no Redis")


def ja_foi_enviado(usuario_id: str, especialidade: str, data: str, horario: str, medico_nome: str) -> bool:
    nome_normalizado = normalizar_nome(medico_nome)
    chave = f"agendamento:{usuario_id}:{especialidade.lower()}:{data}:{horario}:{nome_normalizado}"
    return redis_client.exists(chave) == 1


