from __future__ import annotations

from ai_auditor.ir.model import EdgeKind, NodeKind, OutputKind, Enforcement, StepKind, VarSource
from tests.conftest import fired

HEAD = "        import json\n        from openai import OpenAI\n        client = OpenAI()\n"


def steps_by_name(res):
    return {s.name: s for s in res.ir.llm_steps()}


def test_generic_helper_is_materialized_per_call_site(project):
    res = project({"app.py": HEAD + '''
        def ask(prompt: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "system", "content": "You are a helpful assistant."},
                                                                          {"role": "user", "content": prompt}])
            return r.choices[0].message.content

        def classify(ticket: str) -> str:
            return ask("Classify the ticket as billing or other: " + ticket)

        def summarize(doc: str) -> str:
            return ask("Summarize the document in three bullet points: " + doc)
        '''})
    names = steps_by_name(res)
    assert {"classify", "summarize"} <= set(names)
    assert "ask" not in names
    assert "Classify the ticket" in names["classify"].static_text()


def test_function_with_own_instructions_is_a_step(project):
    res = project({"app.py": HEAD + '''
        def summarize_review(text: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Summarize this review in one sentence: " + text}])
            return r.choices[0].message.content

        def main(rows):
            for row in rows:
                summarize_review(row)
        '''})
    assert "summarize_review" in steps_by_name(res)


def test_taint_branch_labels_and_data_flow(project):
    res = project({"app.py": HEAD + '''
        def route(order: dict) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Pick the queue for this order, review or auto: " + json.dumps(order)}])
            return r.choices[0].message.content

        def reply(route_name: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Write a reply for queue " + route_name}])
            return r.choices[0].message.content

        def main(order, flag):
            q = route(order)
            if q == "review" and flag == "x":
                escalate(order)
            return reply(q)
        '''})
    s = steps_by_name(res)
    g = res.ctx.graph
    controls = g.controlled_branches(s["route"].id)
    assert controls and controls[0].attrs["labels"] == ["review"]  # "x" belongs to `flag`, not to the model output
    assert s["reply"] in g.consumers(s["route"].id)


def test_dead_code_and_constant_false_flags_are_skipped(project):
    res = project({"app.py": HEAD + '''
        LEGACY = False

        def old(raw: str) -> dict:
            if False:
                r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Extract: " + raw}])
                return json.loads(r.choices[0].message.content)
            return {}

        def load(raw: str) -> dict:
            if LEGACY:
                return old(raw)
            return json.loads(raw)
        '''})
    assert not res.ir.llm_steps()


def test_retry_loop_and_kwarg_retries(project):
    res = project({"app.py": HEAD + '''
        def tags(text: str) -> list:
            for attempt in range(3):
                r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Return JSON tags for: " + text}])
                try:
                    return json.loads(r.choices[0].message.content)
                except json.JSONDecodeError:
                    pass
            return []
        '''})
    step = steps_by_name(res)["tags"]
    retries = res.ctx.graph.retry_policies_of(step.id)
    assert retries and retries[0].attrs["trigger"] == "format" and retries[0].attrs["max_attempts"] == 3


def test_structured_output_detection(project):
    res = project({"app.py": HEAD + '''
        from pydantic import BaseModel
        from typing import Literal

        class Verdict(BaseModel):
            label: Literal["spam", "ham"]

        def judge(text: str) -> Verdict:
            r = client.chat.completions.parse(model="gpt-5.5", messages=[{"role": "user", "content": "Is this spam? " + text}], response_format=Verdict)
            return r.choices[0].message.parsed
        '''})
    step = steps_by_name(res)["judge"]
    assert step.output.enforcement == Enforcement.CONSTRAINED and step.output.kind in (OutputKind.SCHEMA, OutputKind.ENUM)
    assert set(step.output.labels) == {"spam", "ham"}


def test_google_config_is_not_structured_output(project):
    res = project({"app.py": '''
        from google import genai
        from google.genai import types
        client = genai.Client()

        def label(text: str) -> str:
            r = client.models.generate_content(model="gemini-2.5-pro", contents="Label: " + text,
                                               config=types.GenerateContentConfig(temperature=0))
            return r.text
        '''})
    assert steps_by_name(res)["label"].output.enforcement != Enforcement.CONSTRAINED


def test_agent_definitions_are_not_sequential_calls(project):
    res = project({"agents_app.py": '''
        import asyncio
        from agents import Agent, Runner

        a = Agent(name="news", instructions="Find recent news about the company and summarize it.", model="gpt-5.5")
        b = Agent(name="filings", instructions="Read the latest filings and list material risks.", model="gpt-5.5")

        async def research(name: str):
            return await asyncio.gather(Runner.run(a, name), Runner.run(b, name))
        '''})
    assert {s.step_kind for s in res.ir.llm_steps()} == {StepKind.AGENT}
    assert not [f for f in res.findings if f.rule_id == "LLM-025" and f.actionable]


def test_claude_code_extraction(project):
    res = project({
        ".claude/agents/planner.md": "---\nname: planner\ndescription: Plans work. Use proactively.\ntools: Read, Grep\nmodel: sonnet\n---\nPlan the change, then ask the implementer agent to do it.\n",
        ".claude/agents/implementer.md": "---\nname: implementer\ndescription: Implements plans.\ntools: Read, Edit, Bash\n---\nImplement the plan.\n",
        "CLAUDE.md": "# Project\nUse uv.\n",
    })
    s = steps_by_name(res)
    assert res.ctx.profile(s["planner"]).model.id == "claude-sonnet-5-5"  # alias resolved by the model catalog
    assert s["implementer"] in res.ctx.graph.delegates_of(s["planner"].id)
    assert res.ir.of_kind(NodeKind.CONTEXT_SOURCE)


def test_variable_sources(project):
    res = project({"app.py": HEAD + '''
        def handle(request):
            question = request.json["question"]
            docs = store.similarity_search(question, k=4)
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": f"Answer {question} using {docs}"}])
            return r.choices[0].message.content
        '''})
    step = steps_by_name(res)["handle"]
    sources = {v.name: v.source for v in step.variables()}
    assert sources.get("docs") == VarSource.RETRIEVAL
    retr = res.ir.of_kind(NodeKind.RETRIEVAL)
    assert retr and retr[0].attrs["top_k"] == 4
    assert any(e.kind == EdgeKind.RETRIEVES for e in res.ir.edges)


# --------------------------------------------------------------------------- code validation of LLM output
VALIDATED_APP = '''
        import json
        import jsonschema
        import anthropic
        from pydantic import BaseModel
        client = anthropic.Anthropic()
        SCHEMA = {"type": "object", "required": ["number", "total"]}

        class Invoice(BaseModel):
            number: str
            total: float

        def extract(text: str) -> dict:
            r = client.messages.create(model="claude-sonnet-5-5", max_tokens=300,
                                       messages=[{"role": "user", "content": "Extract number and total as JSON from: " + text}])
            data = json.loads(r.content[0].text)
            jsonschema.validate(data, SCHEMA)
            assert data["total"] >= 0
            Invoice(**data)
            return data

        def check(data: dict) -> str:
            r = client.messages.create(model="claude-sonnet-5-5", max_tokens=5, messages=[{"role": "user", "content":
                "Validate that the JSON has all required fields and correct data types. Answer yes or no. " + json.dumps(data)}])
            return r.content[0].text

        def run(text):
            return check(extract(text))
        '''


def test_code_validation_of_llm_output_is_extracted(project):
    # regression: VALIDATES edges carried an attribute named `kind` that crashed the whole extraction
    res = project({"app.py": VALIDATED_APP})
    assert not [d for d in res.ir.diagnostics if d.code == "EXTRACTOR_CRASH"]
    from ai_auditor.ir.model import EdgeKind, NodeKind

    vals = [n for n in res.ir.nodes.values() if n.kind == NodeKind.VALIDATION]
    assert {n.attrs["kind"] for n in vals} >= {"schema", "assert"}
    step = next(s for s in res.ir.llm_steps() if s.name == "extract")
    assert any(e.kind == EdgeKind.VALIDATES and e.dst == step.id for e in res.ir.edges)


def test_llm_validator_after_code_schema_validation_is_redundant(project):
    res = project({"app.py": VALIDATED_APP})
    (f,) = fired(res, "LLM-002", "check")
    assert any("code schema validation" in e.description for e in f.evidence)


def test_extractor_crash_degrades_to_a_loud_diagnostic(project, monkeypatch):
    from ai_auditor.parser.python import extractor

    def boom(self):
        raise RuntimeError("synthetic extractor bug")

    monkeypatch.setattr(extractor.PythonProjectExtractor, "extract", boom)
    res = project({"app.py": VALIDATED_APP, ".claude/agents/x.md": "---\nname: x\ndescription: d\n---\nSummarize the diff.\n"})
    crash = [d for d in res.ir.diagnostics if d.code == "EXTRACTOR_CRASH"]
    assert crash and "PARTIAL" in crash[0].message
    assert [s.name for s in res.ir.llm_steps()] == ["x"]  # the rest of the project is still analysed
    from ai_auditor.reporting.render import render_markdown, render_text

    assert "partial results" in render_markdown(res).lower() and "!!" in render_text(res)


def test_constants_from_another_module_are_resolved(project):
    res = project({
        "texts/__init__.py": "",
        "texts/rules.py": '''
        HEADER = "Assign the shipping lane. Respond only with EXPRESS, STANDARD or HOLD.\\n"
        LANES = {"EXPRESS": "total > 500", "HOLD": "country is not ES"}
        ''',
        "app.py": HEAD + '''
        from texts import rules

        def lane(order: dict) -> str:
            body = rules.HEADER + f"Rules: {rules.LANES}\\nOrder: {json.dumps(order)}"
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": body}])
            return r.choices[0].message.content
        '''})
    step = steps_by_name(res)["lane"]
    assert "Assign the shipping lane" in step.static_text()
    sources = {v.name: v.source for v in step.variables()}
    assert sources["rules.LANES"] == VarSource.CONSTANT
    assert next(s for n, s in sources.items() if "order" in n) != VarSource.CONSTANT


def test_join_over_constant_rows_is_folded_into_static_text(project):
    res = project({"app.py": HEAD + '''
        PLANS = [("basic", 5), ("pro", 20)]
        RATES = {"es": "21%", "pt": "23%"}

        def blurb() -> str:
            table = "\\n".join(f"{name}: {price} EUR" for name, price in PLANS)
            vat = ", ".join(f"{k}={v}" for k, v in RATES.items())
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content":
                f"Write a two-sentence blurb for these plans:\\n{table}\\nVAT: {vat}"}])
            return r.choices[0].message.content

        def per_user(user: dict) -> str:
            lines = "\\n".join(f"{k}: {v}" for k, v in user.items())
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": f"Greet this user:\\n{lines}"}])
            return r.choices[0].message.content
        '''})
    steps = steps_by_name(res)
    assert "basic: 5 EUR\npro: 20 EUR" in steps["blurb"].static_text() and "es=21%" in steps["blurb"].static_text()
    assert not steps["blurb"].variables()
    assert [v.source for v in steps["per_user"].variables()] != [VarSource.CONSTANT]
    assert fired(res, "LLM-020", "blurb") and not fired(res, "LLM-020", "per_user")


def test_rebound_local_is_not_constant(project):
    res = project({"app.py": HEAD + '''
        def tone(text: str, formal: bool) -> str:
            style = ["casual"]
            if formal:
                style = load_style()
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": f"Rewrite in {style} style: {text}"}])
            return r.choices[0].message.content
        '''})
    step = steps_by_name(res)["tone"]
    assert all(v.source != VarSource.CONSTANT for v in step.variables())


LC = '''
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model="gpt-5.4-mini")
'''


def test_langchain_helper_with_own_template_is_its_own_step_and_filters_carry_taint(project):
    res = project({"app.py": LC + '''
        EXPAND = ChatPromptTemplate.from_messages([("system", "Expand the search query with synonyms and product codes."),
                                                   ("human", "{q}")])
        KEEP = ChatPromptTemplate.from_messages([("system", "Is the snippet about the same product? Answer yes or no."),
                                                 ("human", "{q}\\n{snippet}")])
        REPLY = ChatPromptTemplate.from_messages([("system", "Answer from the snippets only."), ("human", "{q}\\n{ctx}")])

        def expand(q: str) -> str:
            return (EXPAND | llm).invoke({"q": q}).content

        def keep(q: str, hits: list) -> list:
            chain = KEEP | llm
            out = []
            for h in hits:
                if chain.invoke({"q": q, "snippet": h}).content.startswith("yes"):
                    out.append(h)
            return out

        def reply(q: str, hits: list) -> str:
            q2 = expand(q)
            good = keep(q2, hits)
            ctx = "\\n".join(good)
            return (REPLY | llm).invoke({"q": q2, "ctx": ctx}).content
        '''})
    names = steps_by_name(res)
    assert {"expand", "keep", "reply"} <= set(names)
    flows = {(e.src, e.dst) for e in res.ir.edges if e.kind == EdgeKind.DATA_FLOW}
    assert (names["keep"].id, names["reply"].id) in flows  # the filtered list depends on the LLM verdicts
    assert not fired(res, "LLM-025", "reply")


def test_as_retriever_invoke_is_retrieval_with_full_documents(project):
    res = project({"app.py": LC + '''
        from langchain_chroma import Chroma
        store = Chroma(collection_name="kb")
        WIDE = ChatPromptTemplate.from_messages([("system", "Answer using the documents."), ("human", "{q}\\n{docs}")])

        def wide(q: str) -> str:
            hits = store.as_retriever(search_kwargs={"k": 30}).invoke(q)
            docs = "\\n".join(open(h.metadata["path"]).read() for h in hits)
            return (WIDE | llm).invoke({"q": q, "docs": docs}).content
        '''})
    retr = res.ir.of_kind(NodeKind.RETRIEVAL)
    assert len(retr) == 1 and retr[0].attrs["top_k"] == 30 and retr[0].attrs.get("full_documents")
    assert fired(res, "LLM-016")


def test_template_key_renaming_keeps_parameter_flow(project):
    res = project({"app.py": LC + '''
        ANSWER = ChatPromptTemplate.from_messages([("system", "Answer the question."), ("human", "{q}")])
        SHORTEN = ChatPromptTemplate.from_messages([("system", "Shorten the text to two sentences."), ("human", "{text}")])

        def answer(q: str) -> dict:
            return {"answer": (ANSWER | llm).invoke({"q": q}).content}

        def shorten(result: dict) -> str:
            return (SHORTEN | llm).invoke({"text": result["answer"]}).content

        def handle(q: str) -> str:
            return shorten(answer(q))
        '''})
    names = steps_by_name(res)
    flows = {(e.src, e.dst) for e in res.ir.edges if e.kind == EdgeKind.DATA_FLOW}
    assert (names["answer"].id, names["shorten"].id) in flows


def _nb(cells: list[tuple[str, str]]) -> str:
    import json as _json
    return _json.dumps({"cells": [{"cell_type": t, "source": s.splitlines(keepends=True), "metadata": {}} for t, s in cells],
                        "metadata": {}, "nbformat": 4, "nbformat_minor": 5})


def test_notebook_code_cells_are_extracted(project, tmp_path):
    (tmp_path / "demo.ipynb").write_text(_nb([
        ("markdown", "# Demo\nThis notebook classifies tickets."),
        ("code", "%pip install anthropic\nimport anthropic\nclient = anthropic.AsyncAnthropic()"),
        ("code", "%%bash\necho not python"),
        ("code", "def broken(:\n    pass"),
        ("code", "files = !ls\nr = await client.messages.create(model=\"claude-opus-5-5\", max_tokens=5, messages=[{\"role\": \"user\", "
                 "\"content\": \"Respond only with EXPRESS or STANDARD. If the order total is greater than 500 answer EXPRESS. "
                 "Otherwise answer STANDARD. Order: \" + str(order)}])\nlane = r.content[0].text"),
    ]))
    res = project({})
    steps = res.ir.llm_steps()
    assert len(steps) == 1 and steps[0].location.file == "demo.ipynb"
    assert "If the order total is greater than 500" in steps[0].static_text()
    assert any("cell 4" in d.message for d in res.ir.diagnostics)  # the broken cell is reported, not fatal
    assert not any(d.code == "EXTRACTOR_CRASH" for d in res.ir.diagnostics)


def test_invalid_notebook_is_a_parse_error_not_a_crash(project, tmp_path):
    (tmp_path / "bad.ipynb").write_text("{not json")
    res = project({"ok.py": HEAD})
    assert any(d.code == "PARSE_ERROR" and "bad.ipynb" in d.message for d in res.ir.diagnostics)


def test_notebooks_are_exploratory_by_default(project, tmp_path):
    cell = ("import json, anthropic\nclient = anthropic.Anthropic()\nfor row in rows:\n    client.messages.create(model=\"claude-opus-5-5\", "
            "max_tokens=5, messages=[{\"role\": \"user\", \"content\": \"Decide the shipping lane. Respond only with EXPRESS or STANDARD. "
            "If the order total is greater than 500 answer EXPRESS. If the country is not ES answer STANDARD. Order: \" + json.dumps(row)}])")
    (tmp_path / "batch.ipynb").write_text(_nb([("code", cell)]))
    res = project({})
    assert res.ir.llm_steps() and not [f for f in res.findings if f.actionable]
    assert "notebook" in res.ir.llm_steps()[0].attrs["non_production_reason"]
    (tmp_path / ".ai-auditor.yaml").write_text("notebooks: production\n")
    assert [f for f in project({}).findings if f.actionable]
    (tmp_path / ".ai-auditor.yaml").write_text("notebooks: skip\n")
    assert not project({}).ir.llm_steps()


def test_memory_loading_semantics(project, tmp_path):
    big = "Rule: always run the linters before committing.\n" * 400
    (tmp_path / "AGENTS.md").write_text(big)
    (tmp_path / "CLAUDE.md").symlink_to("AGENTS.md")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "CLAUDE.md").write_text(big)
    res = project({})
    ctxs = {n.name: n for n in res.ir.of_kind(NodeKind.CONTEXT_SOURCE)}
    assert set(ctxs) == {"CLAUDE.md", "pkg/CLAUDE.md"}  # the symlinked AGENTS.md is the same file
    assert ctxs["CLAUDE.md"].attrs["always_loaded"] and ctxs["CLAUDE.md"].attrs["aliases"] == ["AGENTS.md"]
    assert not ctxs["pkg/CLAUDE.md"].attrs["always_loaded"]
    assert [f.component for f in fired(res, "LLM-004")] == ["CLAUDE.md"]


def test_non_production_paths():
    from ai_auditor.parser.python.extractor import non_production_path

    for rel in ("tests/test_app.py", "integration_tests/_state.py", "pkg/samples/demo.py", "docs/snippets/x.py",
                "examples/tools/skills/csv/SKILL.md", "src/app_test.py", "conftest.py"):
        assert non_production_path(rel), rel
    for rel in ("src/app.py", "pkg/latest/run.py", "contest/main.py", "src/testimonials.py", ".claude/agents/tester.md"):
        assert not non_production_path(rel), rel


def test_settings_instance_defaults_resolve_model_and_prompt(project):
    res = project({"settings.py": '''
        from dataclasses import dataclass, field

        @dataclass(frozen=True)
        class LLMSettings:
            fast: str = "gpt-5.5-mini"
            strong: str = field(default="gpt-5.5")
            triage_prompt: str = "Route the ticket to billing, shipping or other. Reply with the queue only."

        SETTINGS = LLMSettings()
        CUSTOM = LLMSettings(strong="o4")
        ''', "app.py": HEAD + '''
        from settings import SETTINGS, CUSTOM

        def triage(ticket: str) -> str:
            r = client.chat.completions.create(model=SETTINGS.strong, messages=[{"role": "system", "content": SETTINGS.triage_prompt},
                                                                               {"role": "user", "content": ticket}])
            return r.choices[0].message.content

        def overridden(ticket: str) -> str:
            r = client.chat.completions.create(model=CUSTOM.strong, messages=[{"role": "user", "content": ticket}])
            return r.choices[0].message.content
        '''})
    names = steps_by_name(res)
    assert names["triage"].model.raw == "gpt-5.5"
    assert "Route the ticket" in names["triage"].static_text()
    assert names["overridden"].model.raw is None  # the keyword overrides the class default


def test_prompt_built_by_a_method_on_self(project):
    res = project({"report.py": HEAD + '''
        class StatusPage:
            header = "Render the rows below as a Markdown table with columns service, state and since."

            def __init__(self, model: str = "gpt-5.5"):
                self.model = model

            def _build(self, rows: list) -> str:
                body = "\\n".join(f"{r['service']}|{r['state']}" for r in rows)
                return f"{self.header}\\n\\n{body}"

            def render(self, rows: list) -> str:
                r = client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": self._build(rows)}])
                return r.choices[0].message.content
        '''})
    step = steps_by_name(res)["render"]
    assert "Markdown table" in step.static_text()
    assert fired(res, "LLM-010", "render")


def test_langchain_helper_with_constant_instructions_is_its_own_step(project):
    res = project({"prompts.py": '''
        CONDENSE = "Shorten the following abstract to two sentences."
        ''', "chain.py": '''
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
        import prompts

        llm = ChatOpenAI(model="gpt-5.5")

        def condense(abstract: str) -> str:
            tmpl = ChatPromptTemplate.from_messages([("system", prompts.CONDENSE), ("human", "{a}")])
            return (tmpl | llm).invoke({"a": abstract}).content

        def card(abstract: str) -> str:
            return condense(abstract)
        '''})
    assert "condense" in steps_by_name(res)


def test_fstring_model_with_constant_parts(project):
    res = project({"agent.py": '''
        from pydantic_ai import Agent
        PROVIDER = "openai"
        BIG = "gpt-5.5"
        tagger = Agent(f"{PROVIDER}:{BIG}", system_prompt="Tag the note with one topic.")
        '''})
    assert steps_by_name(res)["tagger"].model.raw == "gpt-5.5"


def test_join_over_module_constant_is_static_but_not_over_a_filled_local(project):
    res = project({"app.py": HEAD + '''
        TOPICS = ("billing", "shipping", "returns")

        def tag(note: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Topics: " + ", ".join(TOPICS) + "\\n" + note}])
            return r.choices[0].message.content

        def explain(rows: list) -> str:
            lines = []
            for row in rows:
                lines.append(f"{row['k']}: {row['v']}")
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Explain these numbers:\\n" + "\\n".join(lines)}])
            return r.choices[0].message.content
        '''})
    names = steps_by_name(res)
    assert "billing, shipping, returns" in names["tag"].static_text()
    assert any(v.source != VarSource.CONSTANT for v in names["explain"].variables())
