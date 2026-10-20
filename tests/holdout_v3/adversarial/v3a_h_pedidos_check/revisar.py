import json
from pathlib import Path

import litellm

REGLAS = """Cada pedido debe cumplir lo siguiente:
- id: entero positivo
- email: cadena con una arroba y un punto después de ella
- fecha: formato ISO 8601 (AAAA-MM-DD)
- cantidad: entero entre 1 y 20
- zona: uno de norte, sur, este, oeste"""


def revisar_archivo_pedidos(directorio: str) -> list[dict]:
    informe = []
    for ruta in sorted(Path(directorio).glob("*.json")):
        pedido = json.loads(ruta.read_text())
        r = litellm.completion(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": REGLAS + "\nResponde OK si el pedido cumple todo, o lista cada campo que no cumple."},
                {"role": "user", "content": json.dumps(pedido)},
            ],
        )
        informe.append({"archivo": ruta.name, "resultado": r.choices[0].message.content})
    return informe
