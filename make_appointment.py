# 🗂 Bibliotecas
from fastapi import APIRouter

# 💾 Redis
# from redis_utils import recuperar_agendamento

# 📑 Modelos e lifespan
from code_sup import ConfirmacaoAgendamento

# 📅 Agendamento
from booking import agendar_horario


router = APIRouter()


@router.post("/make_appointment")
async def make_appointment(body: ConfirmacaoAgendamento):
    dados = await agendar_horario(
        solicitante_id=body.solicitante_id,
        especialidade=body.especialidade,
        nome_medico=body.nome_profissional,
        data=body.data,
        hora=body.hora,
        nome_paciente=body.nome_paciente,
        cpf=body.CPF,
        data_nascimento=body.data_nascimento,
        contato=body.contato
    )

    if not dados:
        return {"erro": "Falha ao confirmar agendamento. Verifique os dados ou tente novamente."}

    return {"status": "confirmado", "detalhes": dados}
