import os

from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

PERSIST_DIR = os.environ.get("KB_DIR", "./kb_store")

embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
vectorstore = Chroma(
    collection_name="handbook",
    embedding_function=embeddings,
    persist_directory=PERSIST_DIR,
)

big_llm = ChatOpenAI(model="gpt-5.5", temperature=0.2)
small_llm = ChatOpenAI(model="gpt-5.4-mini", temperature=0)

REWRITE_TMPL = ChatPromptTemplate.from_messages(
    [
        ("system", "Rewrite the user's latest question so it can be understood without the chat history. "
                   "Keep product names and error codes verbatim. Output the rewritten question only."),
        ("human", "History:\n{history}\n\nLatest question: {question}"),
    ]
)

GRADE_TMPL = ChatPromptTemplate.from_messages(
    [
        ("system", "Does the passage help answer the question? Answer yes or no. "
                   "Consider whether it addresses the same product and version."),
        ("human", "Question: {question}\n\nPassage:\n{passage}"),
    ]
)

ANSWER_TMPL = ChatPromptTemplate.from_messages(
    [
        ("system", "You are the internal handbook assistant. Answer using only the passages. "
                   "Cite sources as [source: id]. If the passages do not contain the answer, say you do not know."),
        ("human", "Question: {question}\n\nPassages:\n{context}"),
    ]
)

WIDE_TMPL = ChatPromptTemplate.from_messages(
    [
        ("system", "You answer questions about company policy using the full documents provided."),
        ("human", "{question}\n\nDocuments:\n{documents}"),
    ]
)

SUBQ_TMPL = ChatPromptTemplate.from_messages(
    [
        ("system", "Answer the sub-question using the passages. Be brief."),
        ("human", "Sub-question: {sub}\n\nPassages:\n{context}"),
    ]
)

DIGEST_TMPL = ChatPromptTemplate.from_messages(
    [
        ("system", "Summarize the text below in three sentences."),
        ("human", "{text}"),
    ]
)


def rewrite_query(question: str, history: list[tuple[str, str]]) -> str:
    rendered = "\n".join(f"{role}: {msg}" for role, msg in history[-6:])
    chain = REWRITE_TMPL | small_llm
    return chain.invoke({"history": rendered, "question": question}).content.strip()


def grade_passages(question: str, docs) -> list:
    chain = GRADE_TMPL | small_llm
    kept = []
    for doc in docs:
        verdict = chain.invoke({"question": question, "passage": doc.page_content}).content.lower()
        if verdict.startswith("yes"):
            kept.append(doc)
    return kept


def answer_question(question: str, history: list[tuple[str, str]]) -> dict:
    standalone = rewrite_query(question, history)
    docs = vectorstore.similarity_search(standalone, k=6)
    docs = grade_passages(standalone, docs)
    context = "\n\n".join(f"[{d.metadata['id']}] {d.page_content}" for d in docs)
    chain = ANSWER_TMPL | big_llm
    reply = chain.invoke({"question": standalone, "context": context})
    return {"answer": reply.content, "sources": [d.metadata["id"] for d in docs]}


def answer_broad_question(question: str) -> str:
    retriever = vectorstore.as_retriever(search_kwargs={"k": 40})
    docs = retriever.invoke(question)
    documents = "\n\n=====\n\n".join(
        open(d.metadata["path"]).read() for d in docs
    )
    chain = WIDE_TMPL | big_llm
    return chain.invoke({"question": question, "documents": documents}).content


def answer_with_subquestions(question: str, subquestions: list[str]) -> str:
    parts = []
    for sub in subquestions:
        docs = vectorstore.similarity_search(question, k=8)
        context = "\n".join(d.page_content for d in docs)
        chain = SUBQ_TMPL | big_llm
        parts.append(chain.invoke({"sub": sub, "context": context}).content)
    return "\n".join(parts)


def condense_answer(result: dict) -> str:
    chain = DIGEST_TMPL | big_llm
    return chain.invoke({"text": result["answer"]}).content


def handle(question: str, history: list[tuple[str, str]], broad: bool = False) -> str:
    if broad:
        return answer_broad_question(question)
    result = answer_question(question, history)
    if not result["sources"]:
        return "I could not find this in the handbook."
    if len(result["answer"]) > 1200:
        return condense_answer(result)
    return result["answer"]
