import csv
import json
import logging
import sys

import litellm

log = logging.getLogger("nightly_enrich")

CLASSIFIER_MODEL = "gpt-5.5"
WRITER_MODEL = "claude-opus-5-5"

SENTIMENT_SYSTEM = """You are the review-analytics classifier for Harbor Outfitters.

Label the customer review with exactly one sentiment: positive, neutral, negative, or mixed.
Use "mixed" only when the review contains clear praise and clear criticism of different aspects.

Guidelines
- Judge the overall experience of the customer, not the star rating, which may be missing or wrong.
- Reviews are written in everyday language and often include sarcasm, slang, emojis and typos.
- A review that only complains about shipping or packaging is still negative.
- A review that mentions a competitor favourably is at best neutral.
- Ignore promotional text added by the retailer or by the reviewer's signature.
- Questions with no opinion are neutral.
- If the review is written in a language other than English, classify it anyway.

Examples
"Great jacket, fits perfectly" -> positive
"Zipper broke after two washes. Love that for me." -> negative
"Colour is nice but the sleeves are far too short" -> mixed
"Does this come in XL?" -> neutral

Respond with JSON: {"sentiment": "<label>"}.
(Policy notes continue below.)
""" + "\n".join(
    f"Note {i}: when the review concerns product line {i}, apply the same guidelines without exception."
    for i in range(1, 61)
)

DEPARTMENT_SYSTEM = """Write a one-sentence customer-facing description of the retail department identified by the
code, for use on category landing pages. Use friendly, concise language."""

MODERATION_SYSTEM = """Decide whether the review violates our content policy: hate speech, personal data of third
parties, threats, or undisclosed promotion by the seller. Return JSON {"violates": bool, "reason": str}."""

REPLY_SYSTEM = """You write public replies from Harbor Outfitters to negative reviews. Be sincere and specific to
what the reviewer complained about, never defensive, offer a concrete next step, and stay under 90 words."""

DIGEST_SYSTEM = """Write the weekly voice-of-customer digest for the product leadership team from the aggregated
numbers and sample reviews. Explain what moved, hypothesise why, and recommend two actions."""


def classify_review_sentiment(review_text: str) -> str:
    response = litellm.completion(
        model=CLASSIFIER_MODEL,
        messages=[
            {"role": "system", "content": SENTIMENT_SYSTEM},
            {"role": "user", "content": review_text},
        ],
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)["sentiment"]


def describe_department(department_code: str) -> str:
    response = litellm.completion(
        model=CLASSIFIER_MODEL,
        messages=[
            {"role": "system", "content": DEPARTMENT_SYSTEM},
            {"role": "user", "content": f"Department code: {department_code}"},
        ],
    )
    return response.choices[0].message.content.strip()


def flag_policy_violation(review_text: str) -> dict:
    response = litellm.completion(
        model=CLASSIFIER_MODEL,
        messages=[
            {"role": "system", "content": MODERATION_SYSTEM},
            {"role": "user", "content": review_text},
        ],
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


def draft_review_reply(review_text: str, product_name: str) -> str:
    response = litellm.completion(
        model=WRITER_MODEL,
        messages=[
            {"role": "system", "content": REPLY_SYSTEM},
            {"role": "user", "content": f"Product: {product_name}\nReview: {review_text}"},
        ],
        temperature=0.6,
    )
    return response.choices[0].message.content


def write_weekly_digest(stats: dict, samples: list[str]) -> str:
    response = litellm.completion(
        model=WRITER_MODEL,
        messages=[
            {"role": "system", "content": DIGEST_SYSTEM},
            {"role": "user", "content": json.dumps({"stats": stats, "samples": samples}, indent=2)},
        ],
    )
    return response.choices[0].message.content


def main(path: str, out_path: str) -> None:
    counts = {"positive": 0, "neutral": 0, "negative": 0, "mixed": 0}
    samples = []
    with open(path, newline="") as src, open(out_path, "w", newline="") as dst:
        reader = csv.DictReader(src)
        writer = csv.DictWriter(dst, fieldnames=reader.fieldnames + ["sentiment", "dept_blurb", "flagged", "reply"])
        writer.writeheader()
        for i, row in enumerate(reader):
            row["sentiment"] = classify_review_sentiment(row["review_text"])
            row["dept_blurb"] = describe_department(row["department_code"])
            row["flagged"] = flag_policy_violation(row["review_text"])["violates"]
            row["reply"] = ""
            if row["sentiment"] == "negative" and not row["flagged"]:
                row["reply"] = draft_review_reply(row["review_text"], row["product_name"])
            counts[row["sentiment"]] += 1
            if i % 500 == 0:
                samples.append(row["review_text"])
                log.info("processed %s rows", i)
            writer.writerow(row)
    print(write_weekly_digest(counts, samples[:20]))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
