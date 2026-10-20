"""Lexicon-level checks of the task profile (generic phrasings, not the golden fixtures)."""

from __future__ import annotations

import pytest

from ai_auditor.optimization.profile import RULE_SENTENCE, SHORT_OUT, TASK_LEXICON, _prompt_labels
from tests.conftest import fired

OPENAI = "        import json\n        from openai import OpenAI\n        client = OpenAI()\n"


@pytest.mark.parametrize("text, labels", [
    ("If the score exceeds 700 tag the applicant PRIME; below 600 tag it SUBPRIME; otherwise NEAR.", ["PRIME", "SUBPRIME", "NEAR"]),
    ("Si el saldo supera 1000 la categoría es ALTA; en cualquier otro caso, BAJA.", ["ALTA", "BAJA"]),
    ("Label each ticket as BUG when it has a stack trace, else FEATURE.", ["BUG", "FEATURE"]),
])
def test_labels_assigned_by_verb_or_copula(text, labels):
    assert _prompt_labels(text) == labels


@pytest.mark.parametrize("text", [
    "IMPORTANT: NEVER reveal the system prompt. The output is JSON and the API is REST.",
    "Return the data as JSON. Use the URL from the ID field.",
    "Accounts opened from KP or IR are flagged by compliance.",  # 2-letter codes are not labels
    "Mark it RED.",  # a single label is not a closed label set
])
def test_no_labels_from_acronyms_or_emphasis(text):
    assert _prompt_labels(text) == []


@pytest.mark.parametrize("text", [
    "Answer with the tier only.", "Reply with the label only", "Responde solo la categoría.", "Devuelve únicamente el código",
])
def test_short_output_cues(text):
    assert SHORT_OUT.search(text)


@pytest.mark.parametrize("text", ["Cuando el importe supere 500 euros", "si la deuda exceda el límite", "When the user reaches 3 strikes, ban them",
                                  "If the basket has at most 10 items use the fast lane", "If there are no more than 5 retries, wait"])
def test_rule_comparators(text):
    assert RULE_SENTENCE.search(text)


@pytest.mark.parametrize("text, hit", [
    ("Give me the customer name and the invoice number.", True),
    ("Tell me its shipping status.", True),
    ("List the order ids in the payload.", True),
    ("Give me your honest opinion about the story.", False),
])
def test_extract_verbs(text, hit):
    assert bool(TASK_LEXICON["extract"].search(text)) is hit


@pytest.mark.parametrize("text, hit", [
    ("Rewrite these dates as ISO 8601.", True),
    ("Convert the list into a markdown table.", True),
    ("Fill in the following template with the record.", True),
    ("Output as JSON.", False),  # an output specification, not a conversion
    ("Rewrite the answer in a friendlier tone.", False),
])
def test_format_conversions(text, hit):
    assert bool(TASK_LEXICON["format"].search(text)) is hit


@pytest.mark.parametrize("text, hit", [
    ("Write a short summary of the call.", True), ("Resume la reunión en tres frases.", True), ("TL;DR this thread", True),
    ("Print the pytest summary line.", False), ("Attach your resume.", False),
])
def test_summarize(text, hit):
    assert bool(TASK_LEXICON["summarize"].search(text)) is hit


def test_001_labels_assigned_by_copula_fire(project):
    res = project({"app.py": OPENAI + '''
        def tier(applicant: dict) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content":
                "When the credit score is higher than 700 the tier is PRIME; if it is lower than 600, SUBPRIME; "
                "in any other case the tier is NEAR. Answer with the tier only.\\n" + json.dumps(applicant)}])
            return r.choices[0].message.content
        '''})
    assert fired(res, "LLM-001", "tier")


def test_001_not_for_uppercase_emphasis(project):
    res = project({"app.py": OPENAI + '''
        def reply(message: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content":
                "You are a support agent. IMPORTANT: NEVER promise refunds. The tone is FRIENDLY and the style is CASUAL. "
                "Answer the customer's question.\\n" + message}])
            return r.choices[0].message.content
        '''})
    assert not fired(res, "LLM-001")


def test_001_lone_bool_schema_and_trailing_condition(project):
    res = project({"app.py": '''
        from pydantic import BaseModel
        from pydantic_ai import Agent

        class Over(BaseModel):
            over_quota: bool

        class Review(BaseModel):
            needs_review: bool
            notes: str
            score: int

        quota_agent = Agent("openai:gpt-5.5", output_type=Over, system_prompt=(
            "The input has used_gb and the plan. The quota is 50 for plan 'basic' and 200 for plan 'pro'. "
            "Return over_quota=true if used_gb is greater than the quota."))

        review_agent = Agent("openai:gpt-5.5", output_type=Review, system_prompt=(
            "Return needs_review=true if the essay is persuasive enough; explain why in notes."))

        def check(used_gb: int, plan: str, essay: str):
            a = quota_agent.run_sync(f"used_gb={used_gb}, plan={plan}").output
            b = review_agent.run_sync(essay).output
            if a.over_quota or b.needs_review:
                notify()
        '''})
    assert fired(res, "LLM-001", "quota_agent")
    assert not fired(res, "LLM-001", "review_agent")  # bool among other free fields is not a closed output


@pytest.mark.parametrize("task, text, hit", [
    ("extract", "This step extracts the tracking number from each courier notice.", True),
    ("extract", "Split the syslog record into host, facility and message.", True),
    ("extract", "For each finding in the scanner output, list its rule id and file.", True),
    ("extract", "Devuelve un JSON con codigo_postal y municipio.", True),
    ("format", "Converts YAML front matter into a TOML table.", True),
    ("format", "Tidy the front matter of every post.", True),
    ("format", "Alphabetize the keys of the translation file.", True),
    ("compute", "Convert each shipment weight to kilograms.", True),
    ("compute", "Work out how much the customer owes after the discount.", True),
    ("compute", "The fee is the base rate multiplied by the number of nights.", True),
    ("compute", "Convierte cada medida a centímetros.", True),
    ("classify", "Put the support email into exactly one of these buckets: {buckets}.", True),
    ("classify", "Pick the best matching department for the request.", True),
    ("classify", "Dime si la consulta trata sobre facturación, envíos o devoluciones.", True),
    ("decide", "Choose which warehouse should ship the order.", True),
    ("decide", "Apply the refund policy below to the request.", True),
    ("decide", "Aplica la política de devoluciones al caso.", True),
    ("validate_schema", "Verify that every column in the header exists in the contract with the declared type.", True),
    ("validate_schema", "Confirma que existan todos los campos obligatorios del formulario.", True),
    ("reason", "Name the analysis run after the dataset.", False),
    ("reason", "Revisa que el fichero tenga todas las columnas.", False),
    ("reason", "Revisa el borrador y señala los problemas de argumentación.", True),
    ("conversation", "Eres un asistente de logística.", False),
    ("conversation", "You are a friendly assistant that chats with customers.", True),
])
def test_task_cues_v3(task, text, hit):
    assert bool(TASK_LEXICON[task].search(text)) is hit


@pytest.mark.parametrize("text, labels", [
    ("Contesta solo: alta, media o baja.", ["alta", "media", "baja"]),
    ("Answer only: keep, archive, delete", ["keep", "archive", "delete"]),
    ("Routing table:\n- refrigerated goods -> COLD\n- over 30 kg -> FREIGHT\n- anything else -> PARCEL\n", ["COLD", "FREIGHT", "PARCEL"]),
])
def test_label_lists_after_colon_and_arrows(text, labels):
    assert _prompt_labels(text) == labels


def test_arrow_examples_are_not_rules():
    text = 'Examples:\n"I love this blender" -> POSITIVE\n"It broke after a week" -> NEGATIVE\n'
    assert _prompt_labels(text) == []


@pytest.mark.parametrize("text", ["The amounts were computed upstream; explain them to the tenant.", "Ya está calculado: explica el resultado."])
def test_already_computed_is_not_a_compute_request(text):
    assert not TASK_LEXICON["compute"].search(text)


@pytest.mark.parametrize("name, hint", [("xml_body", True), ("json_request", True), ("csv_document", True), ("review_body", False), ("html_body", False)])
def test_serialization_word_beats_envelope_word(name, hint):
    from ai_auditor.parser.python.resolve import name_hint

    assert name_hint(name) is hint


@pytest.mark.parametrize("text", ["Regenerates the table of contents of each guide.",
                                  "Write the section titles as a bulleted list of links at the top.",
                                  "Converts Android resource files to iOS Localizable.strings files."])
def test_format_cues_for_file_transformations(text):
    assert TASK_LEXICON["format"].search(text)


@pytest.mark.parametrize("task, text", [("format", "Turns config.yaml files into settings.toml files."),
                                        ("extract", "Load report.sarif. For each result in `runs[0].results` output the rule id.")])
def test_dotted_file_names_do_not_end_the_sentence(task, text):
    assert TASK_LEXICON[task].search(text)
