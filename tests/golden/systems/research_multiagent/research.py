import asyncio

from agents import Agent, Runner, WebSearchTool, function_tool

MODEL = "gpt-5.5"


@function_tool
def search_arxiv(query: str, max_results: int = 8) -> list[dict]:
    """Search arXiv and return title, authors, abstract and url for each hit."""
    from arxiv_client import search

    return search(query, max_results=max_results)


@function_tool
def run_sql(query: str) -> list[dict]:
    """Run a read-only SQL query against the metrics warehouse."""
    from warehouse import read_only_query

    return read_only_query(query)


web_researcher = Agent(
    name="web_researcher",
    model=MODEL,
    instructions=(
        "Research the question on the open web. Prefer primary sources and recent articles. "
        "Return findings as bullet points with a URL for each claim."
    ),
    tools=[WebSearchTool()],
)

paper_researcher = Agent(
    name="paper_researcher",
    model=MODEL,
    instructions=(
        "Find and read academic papers relevant to the question. Report methodology, sample size and limitations "
        "for each paper, not just the headline result."
    ),
    tools=[search_arxiv],
)

data_analyst = Agent(
    name="data_analyst",
    model=MODEL,
    instructions=(
        "Answer the quantitative part of the question using the warehouse. Write the SQL, run it and interpret "
        "the result, stating any caveats about coverage or time range."
    ),
    tools=[run_sql],
)

research_lead = Agent(
    name="research_lead",
    model=MODEL,
    instructions=(
        "Split the research question into web, academic and quantitative sub-questions and call the three "
        "specialists at the same time. Reconcile contradictions between their findings before replying."
    ),
    tools=[
        web_researcher.as_tool("web_research", "Open-web research"),
        paper_researcher.as_tool("paper_research", "Academic literature research"),
        data_analyst.as_tool("data_analysis", "Quantitative analysis on the warehouse"),
    ],
)

research_orchestrator = Agent(
    name="research_orchestrator",
    model=MODEL,
    instructions=(
        "You receive research requests from users. Pass the request to the research_lead tool exactly as received "
        "and return its answer unchanged."
    ),
    tools=[research_lead.as_tool("lead_research", "Run the full research process")],
)

report_writer = Agent(
    name="report_writer",
    model=MODEL,
    instructions=(
        "Turn the research findings into a decision memo for leadership: a clear recommendation first, then the "
        "evidence, the strongest counter-argument and the open risks. Keep claims tied to the findings."
    ),
)

citation_formatter = Agent(
    name="citation_formatter",
    model=MODEL,
    instructions=(
        "Rewrite each reference in the list as an APA 7 citation. Keep the order and do not add or remove entries."
    ),
)


async def run_research(question: str) -> dict:
    findings = await Runner.run(research_orchestrator, question, max_turns=12)
    memo = await Runner.run(
        report_writer,
        f"Question: {question}\n\nFindings:\n{findings.final_output}",
        max_turns=4,
    )
    refs = await Runner.run(citation_formatter, "\n".join(extract_urls(findings.final_output)), max_turns=2)
    return {"memo": memo.final_output, "references": refs.final_output}


def extract_urls(text: str) -> list[str]:
    import re

    return sorted(set(re.findall(r"https?://\S+", text)))


if __name__ == "__main__":
    print(asyncio.run(run_research("How effective are four-day work weeks for output in software teams?")))
