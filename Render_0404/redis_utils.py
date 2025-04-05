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
    # Normaliza os dados de entrada para garantir consistência
    nome_normalizado = normalizar_nome(medico_nome)
    especialidade = especialidade.lower()

    # Define o padrão para extrair os elementos da chave
    padrao = r"^agendamento:(.*?):(.*?):(.*?):(.*?):(.*?)$"

    # Recupera todas as chaves no Redis relacionadas a agendamentos
    chaves = redis_client.keys("agendamento:*")

    for chave in chaves:
        # Extrai os componentes da chave usando regex
        match = re.match(padrao, chave)
        if match:
            chave_usuario_id, chave_especialidade, chave_data, chave_horario, chave_nome_normalizado = match.groups()

            # Verifica os critérios individualmente
            if (
                    chave_usuario_id == usuario_id and
                    chave_especialidade == especialidade and
                    chave_data == data and
                    chave_horario == horario and
                    chave_nome_normalizado == nome_normalizado
            ):
                # O agendamento já foi enviado
                return True

    # Se não encontrou nenhum registro correspondente, retorna False
    return False


