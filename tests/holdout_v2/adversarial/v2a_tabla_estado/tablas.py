import anthropic


class TableRenderer:
    def __init__(self, model: str = "claude-sonnet-4-5"):
        self.client = anthropic.AsyncAnthropic()
        self.model = model

    def _prompt(self, rows: list[dict]) -> str:
        head = list(rows[0].keys())
        return (
            "Convert the following list of records into a GitHub-flavored Markdown table. "
            f"Columns in this order: {', '.join(head)}. Do not add, remove or change any value.\n\n"
            + "\n".join(str(r) for r in rows)
        )

    async def render_markdown(self, rows: list[dict]) -> str:
        msg = await self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": self._prompt(rows)}],
        )
        return msg.content[0].text

    async def explain_anomalies(self, rows: list[dict], notes: str) -> str:
        msg = await self.client.messages.create(
            model=self.model,
            max_tokens=800,
            messages=[{"role": "user", "content": f"Given these rows and the operator's free-text notes, "
                                                  f"say what looks anomalous and why.\n{rows}\n{notes}"}],
        )
        return msg.content[0].text
