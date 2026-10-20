from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

import prompts_es as P

almacen_politicas = Chroma(
    collection_name="politicas_despacho",
    embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
    persist_directory="./chroma_politicas",
)
almacen_casos = Chroma(
    collection_name="casos_previos",
    embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
    persist_directory="./chroma_casos",
)

llm = ChatOpenAI(model="gpt-4o", temperature=0.2)

SECCIONES = ["Antecedentes", "Análisis", "Riesgos", "Recomendación", "Anexos"]


def responder_consulta_politica(pregunta: str) -> str:
    recuperador = almacen_politicas.as_retriever(search_kwargs={"k": 40})
    docs = recuperador.invoke(pregunta)
    contexto = "\n\n".join(d.page_content for d in docs)
    msgs = [
        SystemMessage(content=P.SISTEMA_CONSULTA),
        HumanMessage(content=f"Contexto:\n{contexto}\n\nPregunta: {pregunta}"),
    ]
    return llm.invoke(msgs).content


def redactar_memo(resumen_asunto: str) -> dict[str, str]:
    memo = {}
    for seccion in SECCIONES:
        previos = almacen_casos.similarity_search(resumen_asunto, k=4)
        antecedentes = "\n---\n".join(d.page_content for d in previos)
        msgs = [
            SystemMessage(content=P.SISTEMA_MEMO.format(seccion=seccion)),
            HumanMessage(content=f"Asunto: {resumen_asunto}\n\nAntecedentes:\n{antecedentes}"),
        ]
        memo[seccion] = llm.invoke(msgs).content
    return memo


def auditar_borrador(borrador: str, politica: str) -> str:
    msgs = [
        SystemMessage(content=P.SISTEMA_AUDITORIA),
        HumanMessage(content=f"POLITICA:\n{politica}\n\nBORRADOR:\n{borrador}"),
    ]
    return llm.invoke(msgs).content
