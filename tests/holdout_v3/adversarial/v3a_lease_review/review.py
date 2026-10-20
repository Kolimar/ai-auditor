from pathlib import Path

from google import genai

client = genai.Client()


def review_lease(path: str, tenant_profile: str) -> str:
    lease_text = Path(path).read_text()
    prompt = f"""You are advising a tenant. Read the whole lease below, cross-reference the clauses
(rent escalation, break options, repair obligations, guarantor liability) and work out, step by step,
which combinations of clauses expose the tenant to costs that are not obvious from any single clause.
Tenant profile: {tenant_profile}

LEASE:
{lease_text}
"""
    response = client.models.generate_content(model="gemini-2.5-pro", contents=prompt)
    return response.text
