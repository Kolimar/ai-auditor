TOOL_SCHEMAS = [
    {
        "name": "search_cases",
        "description": "Search the case-law index.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "read_opinion",
        "description": "Read the full text of an opinion.",
        "input_schema": {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
    },
]


def dispatch(name: str, args: dict) -> str:
    if name == "search_cases":
        return "\n".join(["Doe v. Roe (2011)", "Acme v. Zed (2016)"])
    return "Opinion text for " + args["case_id"]
