import argparse
import json

from llm_steps import (
    assess_statement_consistency,
    check_coverage,
    compute_settlement,
    draft_denial_letter,
    extract_claim_fields,
    summarize_adjuster_notes,
    tag_claim_category,
)
from notices import translate_notice
from settings import SETTINGS


def handle(record: dict, policies: dict) -> dict:
    claim = extract_claim_fields(record["portal_payload"])
    claim["peril"] = record["peril"]
    claim["category"] = tag_claim_category(record["loss_description"])
    policy = policies[claim["policy_number"]]
    decision = check_coverage(claim, policy)
    result = {"claim": claim, "decision": decision}
    if decision.startswith("APPROVE"):
        result["payment"] = compute_settlement(claim, policy)
        result["file_note"] = summarize_adjuster_notes(record.get("adjuster_notes", []))
    elif decision.startswith("DENY"):
        letter = draft_denial_letter(record["claim_ref"], decision)
        result["letter"] = translate_notice(letter, record["language"]) if record.get("language") != "en" else letter
    else:
        result["sui_review"] = assess_statement_consistency(record["statement"], record["police_excerpt"])
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policies", default="data/policies.json")
    args = ap.parse_args()
    policies = json.load(open(args.policies))
    with open(SETTINGS.inbox_path) as fh:
        for line in fh:
            print(json.dumps(handle(json.loads(line), policies)))


if __name__ == "__main__":
    main()
