"""Devin playbooks, Cursor rules and commands, loose Markdown instructions, and the brief for the calling agent."""

from __future__ import annotations

import json

from ai_auditor.config import AuditConfig
from ai_auditor.ir.model import NodeKind
from ai_auditor.parser.discovery import classify
from tests.conftest import fired


def test_classify_devin_and_cursor_files():
    assert classify("playbooks/ship.devin.md") == "devin_playbook"
    assert classify(".cursorrules") == "cursor_rules_file"
    assert classify(".cursor/rules/api/errors.mdc") == "cursor_rule"
    assert classify(".cursor/commands/review.md") == "cursor_command"
    assert classify("notes/ship.md") == "other"
    assert classify("notes/ship.md", loose_md=True) == "loose_md"
    assert classify("notes/README.md", loose_md=True) == "other"


def test_devin_playbook_with_a_fixed_procedure(project):
    res = project({"ops/rotate-logs.devin.md": """
        ## Procedure
        1. Run `make archive-logs`, then `make upload-logs`, then `make prune-logs`.
        2. Report the exit code of each step.

        ## Forbidden actions
        - Running `rm -rf /var/log` by hand.
        """})
    step = next(s for s in res.ir.llm_steps())
    assert (step.name, step.framework) == ("rotate-logs", "devin")
    assert "rm -rf /var/log" not in step.attrs["fixed_commands"]
    assert fired(res, "LLM-017", "rotate-logs")


def test_cursor_rules_load_like_memory_or_skills(project):
    res = project({
        ".cursorrules": "Prefer composition over inheritance.\n",
        ".cursor/rules/style.mdc": "---\ndescription: House style\nalwaysApply: true\n---\nUse two-space indentation.\n",
        ".cursor/rules/data/report.mdc": """
            ---
            description: Use when turning order records into the weekly report table
            ---
            Render the orders JSON array as a Markdown table with the columns order_id, customer and total. Output only the table.
            """,
    })
    always = {n.name: n.attrs["loaded_by"] for n in res.ir.of_kind(NodeKind.CONTEXT_SOURCE) if n.attrs.get("always_loaded")}
    assert always == {".cursorrules": "cursor", ".cursor/rules/style.mdc": "cursor"}
    step = next(s for s in res.ir.llm_steps())
    assert (step.name, step.framework, step.attrs["cc_type"]) == ("report", "cursor", "skill")
    assert fired(res, "LLM-010", "report")


def test_loose_markdown_is_read_only_when_asked(project):
    files = {"playbooks/publish.md": "Run `make docs`, then `make publish`.\n", "playbooks/README.md": "Exported playbooks.\n"}
    assert not project(files).ir.llm_steps()
    res = project(files, config=AuditConfig(markdown_instructions=True))
    assert [(s.name, s.framework) for s in res.ir.llm_steps()] == [("publish", "markdown")]


def test_agent_brief_lists_unsettled_steps_and_weak_findings(project):
    from ai_auditor.reporting.agent_brief import build_brief, render_brief_markdown

    res = project({
        "ship.devin.md": "Run `make lint`, then `make test`, then `make release`.\n",
        "review.devin.md": "Read the design document and argue for and against each trade-off it makes.\n",
    })
    brief = build_brief(res, res.findings)
    assert [s["component"] for s in brief["review"]] == ["review"]
    assert [c["rule"] for c in brief["double_check"]] == ["LLM-017"]
    assert "### To review (1)" in render_brief_markdown(brief)


def test_cli_for_agent(tmp_path, capsys):
    from ai_auditor.cli.main import main

    (tmp_path / "ship.devin.md").write_text("Run `make lint`, then `make test`, then `make release`.\n")
    assert main(["analyze", str(tmp_path), "--no-cache", "-f", "json", "--for-agent"]) == 0
    assert "agent_brief" in json.loads(capsys.readouterr().out)
    assert main(["analyze", str(tmp_path), "--no-cache", "-f", "sarif", "--for-agent"]) == 2


def test_agent_brief_lists_external_pieces(project):
    from ai_auditor.reporting.agent_brief import build_brief, render_brief_markdown

    res = project({
        ".claude/skills/sync/SKILL.md": """
            ---
            name: sync
            description: Sync the shared skills
            ---
            Run `git clone --depth 1 https://github.com/acme/skills.git /tmp/skills`, then `./scripts/install.sh`.
            Then run `npx -y @acme/lint` on what changed and summarise the result.
            """,
        ".mcp.json": '{"mcpServers": {"tracker": {"type": "stdio"}}}',
    })
    brief = build_brief(res, res.findings)
    assert {(e["kind"], e["ref"]) for e in brief["external"]} == {
        ("repo", "https://github.com/acme/skills.git"), ("script", "./scripts/install.sh"),
        ("package", "@acme/lint"), ("mcp", "mcp:tracker"),
    }
    assert "### External pieces (4)" in render_brief_markdown(brief)


def test_a_single_file_is_read_as_instructions(tmp_path):
    from ai_auditor.parser.discovery import discover

    agent = tmp_path / ".claude" / "agents" / "tagger.md"
    agent.parent.mkdir(parents=True)
    agent.write_text("Classify the ticket.\n")
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Run `make lint`.\n")
    assert [sf.kind for sf in discover(agent, [])] == ["claude_agent"]
    assert [sf.kind for sf in discover(prompt, [])] == ["loose_md"]
