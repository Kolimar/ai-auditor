import anthropic
import chromadb
from langchain_anthropic import ChatAnthropic

from plant_config import OPUS, SONNET
from prompts import NCR_TEMPLATE, RCA_PROMPT, SOP_QA_PROMPT, SPC_EXPLAIN_PROMPT

client = anthropic.Anthropic()
ncr_llm = ChatAnthropic(model=SONNET, temperature=0.3)
sop_collection = chromadb.PersistentClient(path=".sop_index").get_or_create_collection("sop_sections")


def write_ncr_report(part: str, lot: str, disposition: str, remarks: str) -> str:
    prompt = NCR_TEMPLATE.format(part=part, lot=lot, disposition=disposition, remarks=remarks)
    return ncr_llm.invoke(prompt).content


def root_cause_analysis(failure_records: list[dict]) -> str:
    lines = [f"{r['date']} | {r['station']} | {r['symptom']} | {r['params']}" for r in failure_records]
    msg = client.messages.create(
        model=OPUS,
        max_tokens=12000,
        thinking={"type": "enabled", "budget_tokens": 8000},
        system=RCA_PROMPT,
        messages=[{"role": "user", "content": "\n".join(lines)}],
    )
    return "\n".join(b.text for b in msg.content if b.type == "text")


def explain_spc_summary(stats: dict) -> str:
    msg = client.messages.create(
        model=SONNET,
        max_tokens=300,
        system=SPC_EXPLAIN_PROMPT,
        messages=[{"role": "user", "content": f"Cp={stats['cp']:.2f}, Cpk={stats['cpk']:.2f}, "
                                              f"mean={stats['mean']:.4f}, sigma={stats['sigma']:.4f}"}],
    )
    return msg.content[0].text


def answer_sop_question(question: str) -> str:
    hits = sop_collection.query(query_texts=[question], n_results=3)
    passages = "\n\n".join(hits["documents"][0])
    msg = client.messages.create(
        model=SONNET,
        max_tokens=500,
        system=SOP_QA_PROMPT,
        messages=[{"role": "user", "content": f"{passages}\n\nQuestion: {question}"}],
    )
    return msg.content[0].text
