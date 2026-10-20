from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o", temperature=0.2)

SECTIONS = ["Emissions", "Water use", "Supply chain", "Governance", "Workforce", "Outlook"]


def evidence_query(company: str) -> str:
    return f"{company} sustainability disclosures annual report"


def draft_section(section: str, company: str, store) -> str:
    docs = store.similarity_search(evidence_query(company), k=8)
    context = "\n\n".join(d.page_content for d in docs)
    prompt = f"Using the evidence, draft the '{section}' section of {company}'s sustainability report.\n\n{context}"
    return llm.invoke(prompt).content


def build_report(company: str, store) -> str:
    parts = []
    for section in SECTIONS:
        parts.append(f"## {section}\n" + draft_section(section, company, store))
    return "\n\n".join(parts)
