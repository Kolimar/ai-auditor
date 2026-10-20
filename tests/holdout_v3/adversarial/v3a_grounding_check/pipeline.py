from langchain_openai import ChatOpenAI
from pydantic import BaseModel


class LabelSummary(BaseModel):
    indications: list[str]
    contraindications: list[str]
    max_daily_dose_mg: int


class Verdict(BaseModel):
    unsupported_claims: list[str]
    ok: bool


writer = ChatOpenAI(model="gpt-4o", temperature=0).with_structured_output(LabelSummary)
auditor = ChatOpenAI(model="gpt-4o", temperature=0).with_structured_output(Verdict)


def summarize_label(label_text: str) -> LabelSummary:
    return writer.invoke(
        "Summarize the following drug label into indications, contraindications and the maximum daily dose in mg.\n\n"
        + label_text
    )


def check_against_source(label_text: str, summary: LabelSummary) -> Verdict:
    prompt = (
        "Compare the summary with the original label. List every statement in the summary that the label does not "
        "support or that contradicts it (for example a dose that differs, a contraindication that is not mentioned). "
        "Set ok to true only if nothing is unsupported.\n\nLABEL:\n"
        + label_text
        + "\n\nSUMMARY:\n"
        + summary.model_dump_json()
    )
    return auditor.invoke(prompt)
