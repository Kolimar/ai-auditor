import json
import sys
from pathlib import Path

from google import genai

import textos

cliente = genai.Client()


def generar_reportes_semanales(ruta_alumnos: str, carpeta_salida: str) -> int:
    """Se ejecuta desde cron los domingos; hay unos 12 000 alumnos."""
    alumnos = json.loads(Path(ruta_alumnos).read_text())
    salida = Path(carpeta_salida)
    salida.mkdir(exist_ok=True)
    for alumno in alumnos:
        r = cliente.models.generate_content(
            model="gemini-2.5-flash",
            contents=textos.REPORTE_SEMANAL.format(datos=json.dumps(alumno["semana"], ensure_ascii=False)),
        )
        (salida / f"{alumno['id']}.txt").write_text(r.text)
    return len(alumnos)


if __name__ == "__main__":
    total = generar_reportes_semanales(sys.argv[1], sys.argv[2])
    print(f"{total} informes escritos")
