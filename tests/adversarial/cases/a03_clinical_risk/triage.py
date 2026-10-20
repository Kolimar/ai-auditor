import anthropic

client = anthropic.Anthropic()

SYSTEM = """Eres un asistente de apoyo a enfermeria de triage. Clasifica el nivel de riesgo
(bajo, medio, alto, emergencia) del mensaje del paciente. Considera sintomas descritos de forma
indirecta ('me aprieta aqui y el brazo se me duerme') y medicacion mencionada. Ante duda, sube un nivel."""


def classify_symptom_risk(message: str) -> str:
    msg = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=10,
        system=SYSTEM,
        messages=[{"role": "user", "content": message}],
    )
    return msg.content[0].text.strip()
