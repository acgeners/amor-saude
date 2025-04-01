# 🗂 Bibliotecas
from fastapi import APIRouter

# 📑 Modelos e lifespan
from code_sup import RequisicaoHorario

# 📆 Horários e datas
from date_times import buscar_primeiro_horario


router = APIRouter()


@router.post("/find_slot")
async def find_slot(body: RequisicaoHorario):
    resultado = await buscar_primeiro_horario(
        body.especialidade,
        body.solicitante_id,  # ✅ adiciona isso aqui
        body.data,
        body.minutos_ate_disponivel or 0
    )

    if isinstance(resultado, str) and resultado.lower().startswith("erro"):
        return {
            "status": "erro",
            "mensagem": resultado,
            "especialidade": body.especialidade,
            "data": body.data
        }

    if resultado is None:
        return {
            "status": "nenhum",
            "mensagem": f"Nenhum horário encontrado para {body.especialidade}.",
            "especialidade": body.especialidade,
            "data": body.data
        }

    if resultado.get("erro"):
        return {
            "status": "erro",
            "mensagem": resultado["erro"]
        }

    return {
        "status": "ok",
        "especialidade": body.especialidade,
        "medico": resultado.get("medico"),
        # "consultorio": resultado.get("consultorio"), TODO verificar se inclui isso
        "data": resultado.get("data"),
        "proximo_horario": resultado["proximo_horario"]
    }