from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate

from settings import CHAT_MODEL, CHROMA_DIR, CROPS

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
llm = ChatOpenAI(model=CHAT_MODEL, temperature=0)

AGRO_PROMPT = ChatPromptTemplate.from_template(
    "You are an agronomy assistant for growers in dry-climate orchards.\n"
    "Use the extension-service material below to answer the grower's question.\n\n"
    "{context}\n\nQuestion: {question}"
)


def _store(collection: str) -> Chroma:
    return Chroma(collection_name=collection, embedding_function=embeddings, persist_directory=CHROMA_DIR)


def agronomy_qa(question: str) -> str:
    docs = _store("extension_bulletins").similarity_search(question, k=25)
    context = "\n\n---\n\n".join(d.page_content for d in docs)
    chain = AGRO_PROMPT | llm
    return chain.invoke({"context": context, "question": question}).content


def answer_from_regional_sources(question: str) -> str:
    snippets = []
    for crop in CROPS:
        retriever = _store(f"guide_{crop}").as_retriever(search_kwargs={"k": 3})
        for doc in retriever.invoke(question):
            snippets.append(f"[{crop}] {doc.page_content}")
    prompt = ChatPromptTemplate.from_template(
        "Answer the question using only the notes below. Say which crop each part applies to.\n"
        "{notes}\n\nQuestion: {q}"
    )
    return (prompt | llm).invoke({"notes": "\n".join(snippets), "q": question}).content
