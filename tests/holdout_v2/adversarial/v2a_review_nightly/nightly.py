import json
import sys
from google import genai

client = genai.Client()
MODEL = "gemini-2.5-flash"


def etiquetar_resenas(src: str, dst: str) -> None:
    with open(src) as fin, open(dst, "w") as fout:
        for line in fin:
            review = json.loads(line)
            r = client.models.generate_content(
                model=MODEL,
                contents="Resume en una frase y etiqueta el tema principal de esta resena de producto:\n"
                         + review["body"],
            )
            review["resumen"] = r.text
            fout.write(json.dumps(review, ensure_ascii=False) + "\n")


def respuesta_en_vivo(pregunta: str) -> str:
    r = client.models.generate_content(model=MODEL, contents=pregunta)
    return r.text


if __name__ == "__main__":
    etiquetar_resenas(sys.argv[1], sys.argv[2])
