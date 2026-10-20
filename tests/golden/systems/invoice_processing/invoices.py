import csv
import io
import json
import logging
import time
from decimal import Decimal

from openai import OpenAI

log = logging.getLogger("invoices")

client = OpenAI()
MODEL = "gpt-5.5"

CSV_PARSE_PROMPT = """The user message is a CSV export from our ERP with the header
invoice_no,vendor_id,issue_date,currency,line_no,sku,qty,unit_price.
Return a JSON object {"invoice_no": str, "vendor_id": str, "issue_date": str, "currency": str,
"lines": [{"line_no": int, "sku": str, "qty": int, "unit_price": float}]}. JSON only."""

CONVERT_PROMPT = """Convert the following invoice JSON into a flat CSV with the columns
invoice_no,vendor_id,issue_date,currency,line_no,sku,qty,unit_price,line_total.
One row per line item, header row first, no commentary."""

TOTALS_PROMPT = """Given these invoice lines, compute subtotal (sum of qty * unit_price), tax at {tax_rate} percent
rounded to 2 decimals, and total. Respond with JSON: {{"subtotal": float, "tax": float, "total": float}}.

Lines:
{lines}"""

CATEGORY_PROMPT = """Classify the expense line description into exactly one category from this list:
software_licenses, hardware, consulting, travel, facilities, marketing, other.
Respond with JSON: {"category": "<category>"}.

Description: """

SCAN_PROMPT = """The text below was produced by OCR from a scanned vendor invoice or credit note. The layout is
irregular and wording varies by vendor ("Amount due", "Balance payable", "Total a pagar"...). Extract the vendor
name, the invoice number, the due date, the total payable and the currency. If a value is not present, use null.
Respond with JSON only.

OCR text:
"""

NOTES_PROMPT = """You are helping an accounts-payable analyst. Below are the free-text notes a vendor attached to an
invoice, and the system's comparison with the purchase order. Explain in plain language for the analyst what
the vendor appears to be claiming, whether the notes justify the discrepancy, and what you would ask the vendor.

Discrepancies:
{discrepancies}

Vendor notes:
{notes}"""


def parse_erp_csv(raw_csv: str) -> dict:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": CSV_PARSE_PROMPT},
            {"role": "user", "content": raw_csv},
        ],
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


def convert_invoice_to_csv(invoice: dict) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": CONVERT_PROMPT},
            {"role": "user", "content": json.dumps(invoice)},
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def compute_invoice_totals(lines: list[dict], tax_rate: float) -> dict:
    prompt = TOTALS_PROMPT.format(tax_rate=tax_rate, lines=json.dumps(lines))
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(response.choices[0].message.content)


def categorize_line(description: str, max_attempts: int = 5) -> str:
    for attempt in range(max_attempts):
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": CATEGORY_PROMPT + description}],
        )
        raw = response.choices[0].message.content
        try:
            return json.loads(raw)["category"]
        except json.JSONDecodeError:
            log.warning("bad json from model on attempt %s", attempt)
            time.sleep(0.5)
    return "other"


def extract_scanned_invoice(ocr_text: str) -> dict:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": SCAN_PROMPT + ocr_text}],
    )
    return json.loads(response.choices[0].message.content)


def explain_vendor_notes(discrepancies: list[str], notes: str) -> str:
    prompt = NOTES_PROMPT.format(discrepancies="\n".join(discrepancies), notes=notes)
    response = client.responses.create(model=MODEL, input=prompt)
    return response.output_text


def draft_vendor_email(vendor_name: str, issues: list[str], tone: str = "courteous") -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You write emails from the accounts-payable team to vendors. Be " + tone
                + ", concrete about what we need, and never admit liability for payment delays.",
            },
            {
                "role": "user",
                "content": f"Vendor: {vendor_name}\nOpen issues:\n" + "\n".join(f"- {i}" for i in issues),
            },
        ],
        temperature=0.6,
    )
    return response.choices[0].message.content


def reconcile(invoice: dict, purchase_order: dict) -> list[str]:
    issues = []
    totals = compute_invoice_totals(invoice["lines"], tax_rate=invoice.get("tax_rate", 21))
    if Decimal(str(totals["total"])) != Decimal(str(purchase_order["expected_total"])):
        issues.append(f"total {totals['total']} != PO {purchase_order['expected_total']}")
    return issues


def process_file(path: str, purchase_order: dict) -> dict:
    raw = open(path, newline="").read()
    invoice = parse_erp_csv(raw)
    for line in invoice["lines"]:
        line["category"] = categorize_line(line["sku"])
    issues = reconcile(invoice, purchase_order)
    result = {"invoice": invoice, "issues": issues}
    if issues and invoice.get("vendor_notes"):
        result["analyst_brief"] = explain_vendor_notes(issues, invoice["vendor_notes"])
    if issues:
        result["vendor_email"] = draft_vendor_email(invoice["vendor_id"], issues)
    buf = io.StringIO(convert_invoice_to_csv(invoice))
    result["rows"] = list(csv.DictReader(buf))
    return result


def process_scan(ocr_text: str) -> dict:
    data = extract_scanned_invoice(ocr_text)
    if data.get("total") is None or data.get("due_date") is None:
        data["needs_human"] = True
    return data
