import json
import subprocess

from openai import OpenAI

client = OpenAI()

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_check",
            "description": "Run a read-only diagnostic command on the host",
            "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]},
        },
    }
]


def _execute(cmd: str) -> str:
    out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    return (out.stdout + out.stderr)[-4000:]


def run_runbook(incident: str) -> str:
    messages = [
        {"role": "system", "content": "Diagnose the incident using diagnostics. Say DONE and give the root cause when sure."},
        {"role": "user", "content": incident},
    ]
    while True:
        resp = client.chat.completions.create(model="gpt-4o", messages=messages, tools=TOOLS)
        msg = resp.choices[0].message
        messages.append(msg)
        if msg.tool_calls:
            for call in msg.tool_calls:
                result = _execute(json.loads(call.function.arguments)["cmd"])
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
            continue
        if msg.content and "DONE" in msg.content:
            return msg.content
