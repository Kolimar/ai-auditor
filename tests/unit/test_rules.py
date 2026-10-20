"""One positive and at least one negative sample per rule, written against docs/RULES.md (not the golden set)."""

from __future__ import annotations

import pytest

from ai_auditor.ir.model import NodeKind
from tests.conftest import fired

# indented like the snippets below so that textwrap.dedent strips one common margin
ANTHROPIC = "        import anthropic\n        client = anthropic.Anthropic()\n"
OPENAI = "        import json\n        from openai import OpenAI\n        client = OpenAI()\n"


# --------------------------------------------------------------------------- LLM-001 deterministic decision
def test_001_explicit_rules_over_structured_input(project):
    res = project({"app.py": ANTHROPIC + '''
        import json
        RULES = """Decide the shipping lane for the order. Respond only with EXPRESS, STANDARD or HOLD.
        - If the order total is greater than 500, answer "EXPRESS".
        - If the country is not "ES", answer "HOLD".
        - Otherwise answer "STANDARD"."""

        def pick_lane(order: dict) -> str:
            r = client.messages.create(model="claude-opus-5-5", max_tokens=5, system=RULES,
                                       messages=[{"role": "user", "content": json.dumps(order)}])
            lane = r.content[0].text.strip()
            if lane == "HOLD":
                notify(order)
            return lane
        '''})
    assert fired(res, "LLM-001", "pick_lane")


def test_001_not_on_free_text_judgment(project):
    res = project({"app.py": ANTHROPIC + '''
        PROMPT = """Read the customer's message and decide if it is a complaint. Pay attention to sarcasm and tone.
        If the customer sounds upset, answer "complaint", otherwise answer "other"."""

        def triage(message: str) -> str:
            r = client.messages.create(model="claude-sonnet-5-5", max_tokens=5, system=PROMPT,
                                       messages=[{"role": "user", "content": message}])
            return r.content[0].text
        '''})
    assert not fired(res, "LLM-001")


# --------------------------------------------------------------------------- LLM-002 redundant validation
def test_002_llm_checks_schema_already_enforced(project):
    res = project({"app.py": OPENAI + '''
        from pydantic import BaseModel

        class Invoice(BaseModel):
            number: str
            total: float

        def extract(text: str) -> Invoice:
            r = client.chat.completions.parse(model="gpt-5.5", messages=[{"role": "user", "content": "Extract the invoice: " + text}],
                                              response_format=Invoice)
            return r.choices[0].message.parsed

        def check(inv) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content":
                "Validate that the JSON has all required fields and correct data types. Answer yes or no. " + inv.model_dump_json()}])
            return r.choices[0].message.content

        def run(text):
            inv = extract(text)
            return check(inv)
        '''})
    assert fired(res, "LLM-002", "check")


def test_002_not_when_checking_semantics(project):
    res = project({"app.py": OPENAI + '''
        from pydantic import BaseModel

        class Answer(BaseModel):
            text: str

        def answer(q: str, docs: str) -> Answer:
            r = client.chat.completions.parse(model="gpt-5.5", messages=[{"role": "user", "content": q + docs}], response_format=Answer)
            return r.choices[0].message.parsed

        def verify(a, docs) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content":
                "Verify that the claims in the answer are supported by the sources. Answer yes or no.\\n" + a.text + docs}])
            return r.choices[0].message.content

        def run(q, docs):
            return verify(answer(q, docs), docs)
        '''})
    assert not fired(res, "LLM-002")


# --------------------------------------------------------------------------- LLM-003 / 018 model size
def test_003_frontier_model_for_formatting(project):
    res = project({"app.py": ANTHROPIC + '''
        def to_iso(date_text: str) -> str:
            r = client.messages.create(model="claude-opus-5-5", max_tokens=20,
                                       messages=[{"role": "user", "content": "Convert this date into ISO 8601. Respond only with the date: " + date_text}])
            return r.content[0].text
        '''})
    assert fired(res, "LLM-003", "to_iso") or fired(res, "LLM-010", "to_iso")


def test_003_not_for_open_generation(project):
    res = project({"app.py": ANTHROPIC + '''
        def write_story(theme: str) -> str:
            r = client.messages.create(model="claude-opus-5-5", max_tokens=2000,
                                       messages=[{"role": "user", "content": "Write a short creative story with a surprising ending about " + theme}])
            return r.content[0].text
        '''})
    assert not fired(res, "LLM-003") and not fired(res, "LLM-018")
    assert any(f.rule_id == "LLM-000" and f.component == "write_story" for f in res.findings)


def test_018_classification_of_free_text_on_large_model(project):
    res = project({"app.py": OPENAI + '''
        PROMPT = """Classify the support ticket into exactly one category: billing, shipping, technical, other.
        Respond with only the category."""

        def classify(ticket_text: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "system", "content": PROMPT},
                                                                          {"role": "user", "content": ticket_text}])
            return r.choices[0].message.content
        '''})
    assert fired(res, "LLM-018", "classify")
    assert not fired(res, "LLM-001", "classify")


# --------------------------------------------------------------------------- LLM-004 / 005 / 014 context & caching
def test_005_repeated_block_across_prompts(project):
    policy = " ".join(f"Policy clause {i}: refunds for category {i} follow the standard thirty day window and require a receipt." for i in range(60))
    res = project({"app.py": ANTHROPIC + f'''
        POLICY = """{policy}"""

        def answer_refund(q: str) -> str:
            r = client.messages.create(model="claude-sonnet-5-5", max_tokens=300, system=POLICY + "\\n\\nAnswer the refund question.",
                                       messages=[{{"role": "user", "content": q}}])
            return r.content[0].text

        def draft_denial(q: str) -> str:
            r = client.messages.create(model="claude-sonnet-5-5", max_tokens=300, system=POLICY + "\\n\\nWrite a polite denial email.",
                                       messages=[{{"role": "user", "content": q}}])
            return r.content[0].text
        '''})
    assert fired(res, "LLM-005")


def test_014_large_static_prefix_without_cache_control(project):
    guide = " ".join(f"Rule {i}: when the ticket mentions product line {i}, route it using the standard matrix and cite the clause." for i in range(220))
    res = project({"app.py": ANTHROPIC + f'''
        GUIDE = """{guide}"""

        def handle(ticket: str) -> str:
            r = client.messages.create(model="claude-sonnet-5-5", max_tokens=200, system=GUIDE,
                                       messages=[{{"role": "user", "content": ticket}}])
            return r.content[0].text

        def main(tickets):
            for t in tickets:
                handle(t)
        '''})
    assert fired(res, "LLM-014", "handle")


def test_014_not_when_cache_control_set(project):
    guide = " ".join(f"Rule {i}: when the ticket mentions product line {i}, route it using the standard matrix and cite the clause." for i in range(220))
    res = project({"app.py": ANTHROPIC + f'''
        GUIDE = """{guide}"""

        def handle(ticket: str) -> str:
            r = client.messages.create(model="claude-sonnet-5-5", max_tokens=200,
                                       system=[{{"type": "text", "text": GUIDE, "cache_control": {{"type": "ephemeral"}}}}],
                                       messages=[{{"role": "user", "content": ticket}}])
            return r.content[0].text
        '''})
    assert not fired(res, "LLM-014")


# --------------------------------------------------------------------------- LLM-008 / 022 output structure
def test_008_retry_on_json_errors(project):
    res = project({"app.py": OPENAI + '''
        def tags(text: str) -> list:
            for attempt in range(4):
                r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Return a JSON list of tags for: " + text}])
                try:
                    return json.loads(r.choices[0].message.content)
                except json.JSONDecodeError:
                    continue
            return []
        '''})
    assert fired(res, "LLM-008", "tags")
    assert not fired(res, "LLM-022", "tags")  # subsumed


def test_022_json_loads_without_structured_outputs(project):
    res = project({"app.py": OPENAI + '''
        def tags(text: str) -> list:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Return a JSON list of tags for: " + text}])
            return json.loads(r.choices[0].message.content)
        '''})
    assert fired(res, "LLM-022", "tags")


def test_022_not_with_response_format(project):
    res = project({"app.py": OPENAI + '''
        def tags(text: str) -> list:
            r = client.chat.completions.create(model="gpt-5.5", response_format={"type": "json_object"},
                                               messages=[{"role": "user", "content": "Return a JSON object with tags for: " + text}])
            return json.loads(r.choices[0].message.content)
        '''})
    assert not fired(res, "LLM-022")


# --------------------------------------------------------------------------- LLM-009 / 010 / 011 / 026 code replacements
def test_009_parse_structured_payload(project):
    res = project({"app.py": OPENAI + '''
        def fields(payload: dict) -> dict:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content":
                "From the following JSON extract the customer name, email and order id. Return JSON only.\\n" + json.dumps(payload)}])
            return json.loads(r.choices[0].message.content)
        '''})
    assert fired(res, "LLM-009", "fields")


def test_009_not_on_free_text(project):
    res = project({"app.py": OPENAI + '''
        def fields(email_body: str) -> dict:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content":
                "Extract the customer name and the order id mentioned in the following email. Return JSON.\\n" + email_body}])
            return json.loads(r.choices[0].message.content)
        '''})
    assert not fired(res, "LLM-009")


def test_010_format_conversion(project):
    res = project({"app.py": OPENAI + '''
        def as_table(rows: list) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content":
                "Convert the following JSON records into a markdown table.\\n" + json.dumps(rows)}])
            return r.choices[0].message.content
        '''})
    assert fired(res, "LLM-010", "as_table")


def test_010_not_for_translation(project):
    res = project({"app.py": OPENAI + '''
        def localize(text: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content":
                "Translate this product description into German, adapting idioms and tone for the local market.\\n" + text}])
            return r.choices[0].message.content
        '''})
    assert not fired(res, "LLM-010")


def test_026_arithmetic(project):
    res = project({"app.py": OPENAI + '''
        def totals(lines: list) -> dict:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content":
                "Calculate the sum of qty * price for these lines and the total with 21% tax. Respond with JSON.\\n" + json.dumps(lines)}])
            return json.loads(r.choices[0].message.content)
        '''})
    assert fired(res, "LLM-026", "totals")


# --------------------------------------------------------------------------- LLM-020 precomputation
def test_020_static_prompt(project):
    res = project({"app.py": ANTHROPIC + '''
        def tips() -> str:
            r = client.messages.create(model="claude-sonnet-5-5", max_tokens=300,
                                       messages=[{"role": "user", "content": "List five general tips for writing a clear bug report."}])
            return r.content[0].text
        '''})
    assert fired(res, "LLM-020", "tips")


def test_020_not_when_variety_requested(project):
    res = project({"app.py": ANTHROPIC + '''
        def joke() -> str:
            r = client.messages.create(model="claude-sonnet-5-5", max_tokens=100, temperature=1.0,
                                       messages=[{"role": "user", "content": "Tell me a random joke, different each time."}])
            return r.content[0].text
        '''})
    assert not fired(res, "LLM-020")


# --------------------------------------------------------------------------- LLM-021 / 024 / 025 architecture
def test_021_while_true_agent_loop(project):
    res = project({"app.py": ANTHROPIC + '''
        def agent(task: str, tools: list) -> str:
            messages = [{"role": "user", "content": task}]
            while True:
                r = client.messages.create(model="claude-sonnet-5-5", max_tokens=1000, tools=tools, messages=messages)
                messages.append({"role": "assistant", "content": r.content})
                if r.stop_reason == "end_turn":
                    break
            return r.content[0].text
        '''})
    assert fired(res, "LLM-021")


def test_021_not_with_bound(project):
    res = project({"app.py": ANTHROPIC + '''
        def agent(task: str, tools: list) -> str:
            messages = [{"role": "user", "content": task}]
            for _ in range(10):
                r = client.messages.create(model="claude-sonnet-5-5", max_tokens=1000, tools=tools, messages=messages)
                messages.append({"role": "assistant", "content": r.content})
                if r.stop_reason == "end_turn":
                    break
            return r.content[0].text
        '''})
    assert not fired(res, "LLM-021")


def test_024_batch_over_csv(project):
    res = project({"job.py": OPENAI + '''
        import csv

        def summarize_review(text: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Summarize this review in one sentence: " + text}])
            return r.choices[0].message.content

        def main(path):
            with open(path) as f:
                for row in csv.DictReader(f):
                    print(summarize_review(row["text"]))

        if __name__ == "__main__":
            main("reviews.csv")
        '''})
    assert fired(res, "LLM-024", "summarize_review")


def test_024_not_in_web_handler(project):
    res = project({"api.py": OPENAI + '''
        import csv
        from fastapi import FastAPI
        app = FastAPI()

        def summarize_review(text: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Summarize this review in one sentence: " + text}])
            return r.choices[0].message.content

        @app.post("/summaries")
        def summaries(path: str):
            with open(path) as f:
                return [summarize_review(row["text"]) for row in csv.DictReader(f)]
        '''})
    assert not fired(res, "LLM-024")


def test_025_independent_sequential_calls(project):
    res = project({"app.py": OPENAI + '''
        def title(doc: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Write a title for this article: " + doc}])
            return r.choices[0].message.content

        def keywords(doc: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Write five SEO keywords for this article: " + doc}])
            return r.choices[0].message.content

        def publish(doc: str) -> dict:
            t = title(doc)
            k = keywords(doc)
            return {"title": t, "keywords": k}
        '''})
    assert fired(res, "LLM-025", "publish")


def test_025_not_when_dependent(project):
    res = project({"app.py": OPENAI + '''
        def outline(doc: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Write an outline for: " + doc}])
            return r.choices[0].message.content

        def expand(outline_text: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Write the article from this outline: " + outline_text}])
            return r.choices[0].message.content

        def publish(doc: str) -> str:
            o = outline(doc)
            return expand(o)
        '''})
    assert not fired(res, "LLM-025")


# --------------------------------------------------------------------------- Claude Code
def test_cc_fixed_command_agent(project):
    res = project({".claude/agents/test-runner.md": '''
        ---
        name: test-runner
        description: Runs the test suite and reports failures.
        tools: Bash
        model: opus
        ---
        Run `uv run pytest -q` and then `uv run ruff check .`. Report the exit codes and the names of failing tests.
        '''})
    assert fired(res, "LLM-017", "test-runner") or fired(res, "LLM-003", "test-runner")


def test_cc_command_allowlist_is_not_a_procedure(project):
    # found on a real ~/.claude: a read-only explorer that *permits* commands is not a fixed command sequence
    res = project({".claude/agents/explore.md": '''
        ---
        name: explore
        description: Read-only code explorer that maps a codebase and answers "where does X happen".
        tools: Read, Grep, Bash
        model: sonnet
        ---
        Run git as `git -C <root> ...`; never assume the current working directory.
        Use Bash ONLY for read-only operations: `ls`, `cat`, `find`, `grep`, `git log`, `git show`.
        Be efficient: `find` for filename patterns, `grep` for symbols. Report file:line references.
        '''})
    assert not fired(res, "LLM-017", "explore")
    assert not fired(res, "LLM-003", "explore")


def test_cc_long_procedure_not_replaced_with_code(project):
    body = "\n        ".join(f"{i}. Read the relevant files, validate the schema of the config, compute what changed, and explain the risk." for i in range(80))
    res = project({".claude/agents/reviewer.md": f'''
        ---
        name: reviewer
        description: Reviews pull requests for design problems.
        tools: Read, Grep, Bash
        ---
        {body}
        '''})
    for rule in ("LLM-001", "LLM-009", "LLM-010", "LLM-011", "LLM-026", "LLM-007"):
        assert not fired(res, rule), rule


def test_cc_identical_copies_deduplicated(project):
    agent = '''
        ---
        name: helper
        description: Helps.
        tools: Read
        ---
        Summarize the file the user points to.
        '''
    res = project({"a/.claude/agents/helper.md": agent, "b/.claude/agents/helper.md": agent})
    assert len([s for s in res.ir.llm_steps() if s.name == "helper"]) == 1
    assert any(d.code == "DUPLICATE_DEFINITION" for d in res.ir.diagnostics)
    assert not fired(res, "LLM-006")


def test_021_not_for_chat_repl_waiting_on_a_person(project):
    res = project({"app.py": ANTHROPIC + '''
        def ask_user() -> str:
            return input("> ")

        def chat():
            history = []
            while True:
                history.append({"role": "user", "content": ask_user()})
                r = client.messages.create(model="claude-sonnet-5-5", max_tokens=500, messages=history)
                history.append({"role": "assistant", "content": r.content[0].text})
        '''})
    assert not fired(res, "LLM-021")


def test_022_not_for_regex_cleanup(project):
    res = project({"app.py": OPENAI + '''
        import re

        def script(topic: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Write a short dialogue about " + topic}])
            return re.sub(r"\\(.*?\\)", "", r.choices[0].message.content)
        '''})
    assert not fired(res, "LLM-022")


def test_015_same_query_against_different_retrievers_is_not_repeated(project):
    res = project({"app.py": '''
        def route(query: str, retrievers: list, stores: dict):
            hits = []
            for r in retrievers:
                hits += r.retrieve(query)
            for name in stores:
                store = stores[name]
                hits += store.similarity_search(query, k=4)
            return hits

        def wasteful(questions: list, store):
            out = []
            for q in questions:
                out.append(store.similarity_search("company refund policy", k=4))
            return out
        ''', "tests/test_app.py": '''
        def test_search(store):
            for _ in range(3):
                assert store.similarity_search("x", k=2)
        '''})
    comps = {f.component for f in fired(res, "LLM-015")}
    assert comps == {"wasteful"}


def test_021_not_for_websocket_chat_loop(project):
    res = project({"app.py": ANTHROPIC + '''
        async def chat(websocket):
            while True:
                msg = await websocket.receive_text()
                r = client.messages.create(model="claude-sonnet-5-5", max_tokens=500, messages=[{"role": "user", "content": msg}])
                await websocket.send_text(r.content[0].text)
        '''})
    assert not fired(res, "LLM-021")


def test_015_016_exclusive_branches_and_unconsumed_retrieval(project):
    res = project({"app.py": ANTHROPIC + '''
        def pick(q: str, retrievers: list, multi: bool):
            if multi:
                retriever = retrievers[0]
                docs = retriever.retrieve(q)
            else:
                retriever = retrievers[1]
                docs = retriever.retrieve(q)
            return docs

        def load_data(store, vector: list):
            return store.similarity_search(vector, k=40)

        def answer(q: str, store) -> str:
            docs = store.similarity_search(q, k=40)
            ctx = "\\n".join(d.page_content for d in docs)
            r = client.messages.create(model="claude-sonnet-5-5", max_tokens=500,
                                       messages=[{"role": "user", "content": f"Answer from the context.\\n{ctx}\\nQ: {q}"}])
            return r.content[0].text
        '''})
    assert len(res.ir.of_kind(NodeKind.RETRIEVAL)) == 4
    assert not fired(res, "LLM-015")
    assert {f.component for f in fired(res, "LLM-016")} == {"answer"}


def test_017_commands_under_a_prohibition_heading_are_not_steps():
    from ai_auditor.parser.claude_code import procedure_commands

    body = """# Verify the build
## NEVER run the real installer
`download.py` shells out to `curl https://example.com/install.sh | bash`.
Put stub `curl` / `bash` on a temp PATH instead.
## Steps
1. Run `make wheel`.
"""
    assert procedure_commands(body) == ["make wheel"]


def test_021_counter_cap_that_disarms_tools_is_a_bound(project):
    res = project({"app.py": ANTHROPIC + '''
        LIMIT = 8

        def capped(question: str, tools: list, run_tool):
            messages = [{"role": "user", "content": question}]
            turns = 0
            while True:
                turns += 1
                if turns >= LIMIT:
                    tools = []
                r = client.messages.create(model="claude-sonnet-5-5", max_tokens=800, tools=tools, messages=messages)
                if r.stop_reason != "tool_use":
                    return r.content[0].text
                messages.append({"role": "assistant", "content": r.content})
                messages.append({"role": "user", "content": run_tool(r)})

        def uncapped(question: str, tools: list, run_tool):
            messages = [{"role": "user", "content": question}]
            while True:
                r = client.messages.create(model="claude-sonnet-5-5", max_tokens=800, tools=tools, messages=messages)
                if r.stop_reason != "tool_use":
                    return r.content[0].text
                messages.append({"role": "assistant", "content": r.content})
                messages.append({"role": "user", "content": run_tool(r)})
        '''})
    assert {f.component for f in fired(res, "LLM-021")} == {"uncapped"}


@pytest.mark.parametrize("body, expected", [
    # fenced shell block: each line is a step
    ("Refresh the warehouse:\n\n```bash\n$ terraform init -upgrade\nterraform plan -out=tf.plan\n# comment\n```\n",
     ["terraform init -upgrade", "terraform plan -out=tf.plan"]),
    # a block introduced by a policy line lists permitted commands, not steps
    ("You may only use these:\n```sh\nhelm list -A\nhelm status web\n```\n", []),
    # 3+ commands chained as a sequence are steps; the same commands enumerated are an allowlist
    ("Run `pnpm install`, then `pnpm build`, then `pnpm publish --tag next`.", ["pnpm install", "pnpm build", "pnpm publish --tag next"]),
    ("Useful tools: `pnpm install`, `pnpm build`, `pnpm publish --tag next`.", []),
    # the policy filter applies per sentence, not per line
    ("Run `rake db:migrate` and `rake spec`. Do not touch the seeds.", ["rake db:migrate", "rake spec"]),
    # backticked prose and code are not commands
    ("Set `user_id field` and `\"key\" = \"value\";` in the file.", []),
])
def test_017_fixed_command_extraction(body, expected):
    from ai_auditor.parser.claude_code import procedure_commands

    assert procedure_commands(body) == expected


def test_024_batch_over_file_loaded_with_read_text(project):
    res = project({"nightly.py": OPENAI + '''
        import yaml
        from pathlib import Path

        def nightly(manifest: str):
            products = yaml.safe_load(Path(manifest).read_text())
            for product in products:
                r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Write a teaser for: " + product["name"]}])
                Path(product["slug"] + ".txt").write_text(r.choices[0].message.content)

        if __name__ == "__main__":
            nightly("catalog.yaml")
        '''})
    assert fired(res, "LLM-024", "nightly")


def test_006_summary_of_a_summary_through_nested_calls(project):
    res = project({"brief.py": OPENAI + '''
        def digest(minutes: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Summarize these meeting minutes: " + minutes}])
            return r.choices[0].message.content

        def headline(text: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Summarize the text in one line: " + text}])
            return r.choices[0].message.content

        def brief(minutes: str) -> str:
            return headline(digest(minutes))
        '''})
    assert fired(res, "LLM-006", "headline")


def test_012_forwarder_is_not_excused_by_the_delegates_own_tools(project):
    res = project({
        ".claude/agents/intake.md": "---\nname: intake\ndescription: Entry point for questions about the codebase.\ntools: Task\nmodel: opus\n---\n"
                                    "Pass every question to the code-explorer agent and return its answer unchanged.\n",
        ".claude/agents/code-explorer.md": "---\nname: code-explorer\ndescription: Answers questions about the code.\ntools: Read, Grep, Glob\n"
                                           "model: haiku\n---\nSearch the repository and answer the question with file references.\n",
        ".claude/agents/release-captain.md": "---\nname: release-captain\ndescription: Cuts releases.\ntools: Task, Bash\nmodel: sonnet\n---\n"
                                             "Run the release checklist, then ask the code-explorer agent for anything unclear.\n",
    })
    assert {f.component for f in fired(res, "LLM-012")} == {"intake"}


def test_004_one_disproportionate_cc_description(project):
    topics = ", ".join(f"topic number {i} about the house style for writing" for i in range(80))
    res = project({
        ".claude/agents/style-guide.md": f"---\nname: style-guide\ndescription: Answers style questions about {topics}.\ntools: Read\n---\nAnswer the question.\n",
        ".claude/agents/fixer.md": "---\nname: fixer\ndescription: Fixes failing tests. Use after a red CI run.\ntools: Read, Edit, Bash\n---\nFix the tests.\n",
    })
    assert {f.component for f in fired(res, "LLM-004")} == {"style-guide"}


def test_020_parameter_typed_as_enum_is_a_finite_domain(project):
    res = project({"tiers.py": '''
        from enum import Enum

        class Plan(str, Enum):
            FREE = "free"
            TEAM = "team"
            ENTERPRISE = "enterprise"
        ''', "copy.py": OPENAI + '''
        from tiers import Plan

        def upgrade_blurb(plan: Plan) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": f"Write a two-line upgrade pitch for the {plan.value} plan."}])
            return r.choices[0].message.content

        def pitch_for(customer_note: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": f"Write a two-line upgrade pitch for this customer: {customer_note}"}])
            return r.choices[0].message.content
        '''})
    assert {f.component for f in fired(res, "LLM-020")} == {"upgrade_blurb"}


def test_020_project_function_of_an_enum_parameter(project):
    res = project({"shop.py": OPENAI + '''
        from typing import Literal

        Aisle = Literal["bakery", "dairy", "produce"]
        NAMES = {"bakery": "Fresh bread", "dairy": "Milk & cheese", "produce": "Fruit & veg"}

        def display_name(aisle: Literal["bakery", "dairy", "produce"]) -> str:
            return NAMES[aisle]

        def aisle_sign(aisle: Literal["bakery", "dairy", "produce"]) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": f"Write a short sign for the {display_name(aisle)} aisle."}])
            return r.choices[0].message.content
        '''})
    assert fired(res, "LLM-020", "aisle_sign")


def test_004_history_growth_bounded_by_the_loop_cap(project):
    res = project({"agent.py": ANTHROPIC + '''
        MAX_TURNS = 5

        def short_agent(task: str, tools: list, run_tool):
            messages = [{"role": "user", "content": "Find the root cause and report it. Task: " + task}]
            for _ in range(MAX_TURNS):
                r = client.messages.create(model="claude-sonnet-5-5", max_tokens=800, tools=tools, messages=messages)
                if r.stop_reason != "tool_use":
                    return r.content[0].text
                messages.append({"role": "assistant", "content": r.content})
                messages.append({"role": "user", "content": run_tool(r)})

        def long_agent(task: str, tools: list, run_tool):
            messages = [{"role": "user", "content": "Find the root cause and report it. Task: " + task}]
            while True:
                r = client.messages.create(model="claude-sonnet-5-5", max_tokens=800, tools=tools, messages=messages)
                if r.stop_reason != "tool_use":
                    return r.content[0].text
                messages.append({"role": "assistant", "content": r.content})
                messages.append({"role": "user", "content": run_tool(r)})
        '''})
    assert "short_agent" not in {f.component for f in fired(res, "LLM-004")}


def test_006_cc_agent_that_condenses_another_agents_summaries(project):
    res = project({
        ".claude/agents/ticket-digest.md": "---\nname: ticket-digest\ndescription: Summarizes each support ticket into a short digest file.\n"
                                           "tools: Read, Write\nmodel: sonnet\n---\nRead the ticket and write digests/<id>.md with the problem and the fix.\n",
        ".claude/agents/weekly-recap.md": "---\nname: weekly-recap\ndescription: Weekly recap for the support lead.\ntools: Read, Write\nmodel: sonnet\n---\n"
                                          "Read the digests written by the ticket-digest agent and summarize them into recap.md, one line per ticket.\n",
        ".claude/agents/triage-helper.md": "---\nname: triage-helper\ndescription: Helps triage.\ntools: Read\nmodel: sonnet\n---\n"
                                          "Ask the ticket-digest agent for a digest when a ticket is long, then propose a priority.\n",
    })
    assert {f.component for f in fired(res, "LLM-006")} == {"weekly-recap"}


def test_004_long_description_with_routing_examples_is_not_flagged_alone(project):
    examples = "\n".join(f"  <example>user: question {i} about the build pipeline and its caches. assistant: uses this agent</example>" for i in range(8))
    res = project({".claude/agents/build-doctor.md": f"---\nname: build-doctor\ndescription: |\n  Use when a build fails.\n{examples}\ntools: Read, Bash\n---\nDiagnose the build.\n"})
    assert not fired(res, "LLM-004")


def test_017_a_bare_directory_is_not_a_command():
    from ai_auditor.parser.claude_code import procedure_commands

    assert procedure_commands("Copy the files from `scripts/` and run `scripts/release.sh --dry-run`.") == ["scripts/release.sh --dry-run"]


def test_017_heredoc_bodies_and_continuations_in_shell_blocks():
    from ai_auditor.parser.claude_code import procedure_commands

    body = "```bash\nmake dist \\\n  --jobs 4\ncat > stub.sh <<'EOF'\nexit ${CODE:-0}\nEOF\nmake check\n```\n"
    assert procedure_commands(body) == ["make dist --jobs 4", "cat > stub.sh <<'EOF'", "make check"]
