import argparse
import csv

import anthropic
from pydantic_ai import Agent

from prompts import COVER_LETTER_SCORE, PLANNER_SYSTEM

client = anthropic.Anthropic()

interview_planner = Agent(
    "anthropic:claude-sonnet-4-5",
    system_prompt=PLANNER_SYSTEM,
)


def plan_loop(role: str, cv: str) -> str:
    result = interview_planner.run_sync(f"ROLE:\n{role}\n\nCV:\n{cv}")
    return result.output


def nightly_rescore(path: str, out_path: str) -> None:
    with open(path, newline="") as src, open(out_path, "w", newline="") as dst:
        reader = csv.DictReader(src)
        writer = csv.writer(dst)
        writer.writerow(["candidate_id", "motivation_score"])
        for row in reader:
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=3,
                system=COVER_LETTER_SCORE,
                messages=[{"role": "user", "content": row["cover_letter"]}],
            )
            writer.writerow([row["candidate_id"], resp.content[0].text.strip()])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--out", default="scores.csv")
    args = parser.parse_args()
    nightly_rescore(args.csv_path, args.out)


if __name__ == "__main__":
    main()
