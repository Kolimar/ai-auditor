import asyncio
import json

from agents import Runner

from agentes import (
    asistente_ciudadano,
    calculadora,
    recepcion,
    redactor,
    revisor_juridico,
    validador,
)


async def atender_mensaje(texto: str):
    resultado = await Runner.run(recepcion, texto, max_turns=6)
    return resultado.final_output


async def tramitar_obra_menor(expediente: dict) -> dict:
    datos = json.dumps(expediente, ensure_ascii=False)
    veredicto = await Runner.run(validador, datos, max_turns=2)
    if not str(veredicto.final_output).startswith("VALIDO"):
        return {"estado": "requiere_subsanacion", "detalle": veredicto.final_output}

    tasa = await Runner.run(
        calculadora,
        f"superficie_m2={expediente['superficie_m2']}, valor_obra_eur={expediente['valor_obra']}, "
        f"suelo_protegido={expediente.get('suelo_protegido', False)}",
        max_turns=2,
    )

    borrador = await Runner.run(redactor, f"Expediente:\n{datos}\nTasa liquidada: {tasa.final_output} EUR")
    revision = await Runner.run(revisor_juridico, borrador.final_output, max_turns=4)
    while not str(revision.final_output).startswith("CONFORME"):
        borrador = await Runner.run(
            redactor,
            f"Borrador anterior:\n{borrador.final_output}\nObservaciones del revisor:\n{revision.final_output}",
        )
        revision = await Runner.run(revisor_juridico, borrador.final_output, max_turns=4)
    return {"estado": "borrador_listo", "tasa": tasa.final_output, "resolucion": borrador.final_output}


async def portal_chat() -> None:
    historial = []
    while True:
        pregunta = input("ciudadano> ")
        if pregunta.lower() in {"salir", "adios"}:
            break
        historial.append({"role": "user", "content": pregunta})
        res = await Runner.run(asistente_ciudadano, historial, max_turns=4)
        historial = res.to_input_list()
        print(res.final_output)


if __name__ == "__main__":
    asyncio.run(portal_chat())
