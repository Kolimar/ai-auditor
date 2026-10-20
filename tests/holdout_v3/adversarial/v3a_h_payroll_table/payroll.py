import json

from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-sonnet-4-5", temperature=0)


def _layout_instructions() -> str:
    return (
        "Dispón el registro como una tabla de dos columnas, Campo y Valor, separadas por barras verticales, "
        "una fila por campo, con las fechas escritas DD/MM/YYYY y los importes con dos decimales. "
        "No añadas comentarios ni cambies ningún dato."
    )


async def render_pay_slip(employee: dict) -> str:
    message = _layout_instructions() + "\n\n" + json.dumps(employee, ensure_ascii=False)
    out = await llm.ainvoke(message)
    return out.content


async def flag_unusual_notes(notes: str) -> str:
    out = await llm.ainvoke(
        "Read the manager's free-form notes and say whether they hint at a dispute or a complaint that HR should "
        "look at, with one sentence of justification.\n\n" + notes
    )
    return out.content
