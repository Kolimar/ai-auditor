from langchain_anthropic import ChatAnthropic
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import OpenAIEmbeddings

import textos

modelo_grande = ChatAnthropic(model="claude-sonnet-4-5", max_tokens=1500)
modelo_corto = ChatAnthropic(model="claude-sonnet-4-5", max_tokens=300)

materiales = Chroma(
    collection_name="materiales_curso",
    embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
    persist_directory="./indice_curso",
)


def resumir_leccion(transcripcion: str) -> str:
    plantilla = ChatPromptTemplate.from_messages(
        [("system", textos.RESUMEN_LECCION), ("human", "{texto}")]
    )
    return (plantilla | modelo_grande).invoke({"texto": transcripcion}).content


def condensar_resumen(resumen: str) -> str:
    plantilla = ChatPromptTemplate.from_messages(
        [("system", textos.RESUMEN_DEL_RESUMEN), ("human", "{texto}")]
    )
    return (plantilla | modelo_corto).invoke({"texto": resumen}).content


def explicar_paso_a_paso(problema: str) -> str:
    plantilla = ChatPromptTemplate.from_messages([("system", textos.TUTOR), ("human", "{problema}")])
    return (plantilla | modelo_grande).invoke({"problema": problema}).content


def responder_con_materiales(pregunta: str) -> str:
    fragmentos = materiales.similarity_search(pregunta, k=4)
    contexto = "\n\n".join(f.page_content for f in fragmentos)
    plantilla = ChatPromptTemplate.from_messages(
        [("system", textos.RESPUESTA_CURSO), ("human", "Contexto:\n{contexto}\n\nPregunta: {pregunta}")]
    )
    return (plantilla | modelo_grande).invoke({"contexto": contexto, "pregunta": pregunta}).content


def ficha_de_clase(transcripcion: str) -> str:
    return condensar_resumen(resumir_leccion(transcripcion))
