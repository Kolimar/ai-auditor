import os

from agents import Agent

import prompts_es as P
from herramientas import buscar_oficina, consultar_normativa, estado_expediente

MODELO = os.getenv("PERMISOS_MODELO", "gpt-4.1")
MODELO_LIGERO = os.getenv("PERMISOS_MODELO_LIGERO", "gpt-4.1-mini")

asesor_obras = Agent(
    name="AsesorObras",
    instructions=P.ASESOR_OBRAS,
    model=MODELO,
    tools=[consultar_normativa, estado_expediente],
)

reenviador = Agent(
    name="Reenviador",
    instructions=P.REENVIADOR,
    model=MODELO_LIGERO,
    handoffs=[asesor_obras],
)

calculadora = Agent(
    name="CalculadoraTasas",
    instructions=P.CALCULADORA,
    model=MODELO,
)

validador = Agent(
    name="ValidadorExpediente",
    instructions=P.VALIDADOR,
    model=MODELO_LIGERO,
)

redactor = Agent(
    name="RedactorResolucion",
    instructions=P.REDACTOR,
    model=MODELO,
)

revisor_juridico = Agent(
    name="RevisorJuridico",
    instructions=P.REVISOR_JURIDICO,
    model=MODELO,
    tools=[consultar_normativa],
)

recepcion = Agent(
    name="Recepcion",
    instructions=P.RECEPCION,
    model=MODELO_LIGERO,
    handoffs=[reenviador, asesor_obras],
    tools=[estado_expediente],
)

asistente_ciudadano = Agent(
    name="AsistenteCiudadano",
    instructions=P.ASISTENTE_CIUDADANO,
    model=MODELO_LIGERO,
    tools=[buscar_oficina],
)
