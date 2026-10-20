from __future__ import annotations

import socket
import textwrap
from pathlib import Path

import pytest

from ai_auditor.audit import audit


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """The auditor must never touch the network by default (no LLM calls, no price fetches)."""

    def guard(*args, **kwargs):
        raise AssertionError(f"network access attempted: {args[:1]}")

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket, "create_connection", guard)


@pytest.fixture
def project(tmp_path: Path):
    """Write files {relpath: source} into a temporary project and audit it."""

    def make(files: dict[str, str], **kw):
        for rel, text in files.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(textwrap.dedent(text).lstrip())
        return audit(tmp_path, use_cache=False, **kw)

    return make


def fired(res, rule: str, component: str | None = None) -> list:
    return [f for f in res.findings if f.actionable and f.rule_id == rule and (component is None or f.component == component)]
