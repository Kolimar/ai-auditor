import anthropic

client = anthropic.Anthropic()

TOOLS = [
    {
        "name": "grep_logs",
        "description": "Search service logs for a pattern within a time window.",
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}, "minutes": {"type": "integer"}},
            "required": ["pattern"],
        },
    },
    {
        "name": "get_deploys",
        "description": "List deployments for a service in the past day.",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string"}},
            "required": ["service"],
        },
    },
]


def run_tool(name: str, args: dict) -> str:
    return "..."


def diagnose_root_cause(alert_summary: str) -> str:
    messages = [{"role": "user", "content": f"Investigate and find the most likely root cause.\n{alert_summary}"}]
    for _ in range(12):
        resp = client.messages.create(
            model="claude-opus-4-1",
            max_tokens=2000,
            tools=TOOLS,
            messages=messages,
        )
        if resp.stop_reason != "tool_use":
            return resp.content[0].text
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": run_tool(block.name, block.input)}
                )
        messages.append({"role": "user", "content": results})
    return "no conclusion reached"


def draft_postmortem(timeline: str, log_excerpts: str, root_cause: str) -> str:
    resp = client.messages.create(
        model="claude-opus-4-1",
        max_tokens=3000,
        system="Write a blameless postmortem: impact, timeline, contributing factors, what went well, action items.",
        messages=[
            {
                "role": "user",
                "content": f"Root cause: {root_cause}\n\nTimeline:\n{timeline}\n\nLogs:\n{log_excerpts}",
            }
        ],
    )
    return resp.content[0].text
