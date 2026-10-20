import asyncio
from google import genai

client = genai.Client()

MODEL = "gemini-2.5-pro"


async def assess_contract(text: str) -> str:
    r = await client.aio.models.generate_content(
        model=MODEL, contents="Identify legal risks in this vendor contract and rank them:\n" + text
    )
    return r.text


async def assess_security(questionnaire: str) -> str:
    r = await client.aio.models.generate_content(
        model=MODEL, contents="Assess the security posture described in this questionnaire and flag gaps:\n" + questionnaire
    )
    return r.text


async def assess_financials(statement: str) -> str:
    r = await client.aio.models.generate_content(
        model=MODEL, contents="Analyze the vendor's financial stability from this statement:\n" + statement
    )
    return r.text


async def vendor_review(docs: dict) -> dict:
    contract, security, financials = await asyncio.gather(
        assess_contract(docs["contract"]),
        assess_security(docs["security"]),
        assess_financials(docs["financials"]),
    )
    return {"contract": contract, "security": security, "financials": financials}
