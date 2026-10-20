"""The IR cache is keyed by the extractor versions: any change to the extracted IR must bump them.

If this fails after an intended extractor change: bump EXTRACTOR_VERSION in parser/python/extractor.py and/or
parser/claude_code.py, then refresh the fingerprint with `AI_AUDITOR_REFRESH_FINGERPRINT=1 pytest tests/regression`.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from ai_auditor.parser.claude_code import EXTRACTOR_VERSION as CC_VERSION
from ai_auditor.parser.project import extract_project
from ai_auditor.config import AuditConfig
from ai_auditor.parser.python.extractor import EXTRACTOR_VERSION as PY_VERSION

REPO = Path(__file__).resolve().parents[2]
STORED = Path(__file__).with_name("ir_fingerprint.json")


def _canon(x):
    if isinstance(x, dict):  # token estimates depend on whether tiktoken is installed
        return {k: _canon(v) for k, v in x.items() if "tokens" not in k}
    if isinstance(x, list):
        return sorted((_canon(v) for v in x), key=lambda v: json.dumps(v, sort_keys=True, default=str))
    return x


def _fingerprint() -> str:
    h = hashlib.sha256()
    for root in sorted(d for d in (REPO / "tests" / "golden" / "systems").iterdir() if d.is_dir()):
        ir, _ = extract_project(root, AuditConfig(), use_cache=False)
        d = ir.to_dict()
        d.pop("root", None)
        h.update(json.dumps(_canon(d), sort_keys=True, default=str).encode())
    return h.hexdigest()


def test_ir_changes_come_with_a_version_bump():
    current = {"py": PY_VERSION, "cc": CC_VERSION, "ir": _fingerprint()}
    if os.environ.get("AI_AUDITOR_REFRESH_FINGERPRINT"):
        STORED.write_text(json.dumps(current, indent=1) + "\n")
    stored = json.loads(STORED.read_text())
    if current["ir"] != stored["ir"]:
        assert (current["py"], current["cc"]) != (stored["py"], stored["cc"]), "extracted IR changed: bump EXTRACTOR_VERSION"
        raise AssertionError("extractor version bumped: refresh the fingerprint (AI_AUDITOR_REFRESH_FINGERPRINT=1)")
    assert (current["py"], current["cc"]) == (stored["py"], stored["cc"]), "version bumped without an IR change: refresh"
