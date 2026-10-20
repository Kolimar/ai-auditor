from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from config import CHROMA_DIR, COLECCION, MODELOS
from prompts_es import PLANTILLA_RAG

_almacen = Chroma(
    collection_name=COLECCION,
    persist_directory=CHROMA_DIR,
    embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
)
_llm = ChatOpenAI(model=MODELOS["chat"], temperature=0.2)


def responder_consulta_comprador(pregunta: str) -> str:
    recuperador = _almacen.as_retriever(search_kwargs={"k": 25})
    docs = recuperador.invoke(pregunta)
    contexto = "\n\n".join(d.page_content for d in docs)
    msg = _llm.invoke(PLANTILLA_RAG.format(contexto=contexto, pregunta=pregunta))
    return msg.content
