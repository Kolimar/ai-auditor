import asyncio
from agents import Agent, Runner, WebSearchTool, function_tool


@function_tool
def query_sec_filings(ticker: str) -> str:
    """Fetch recent SEC filings text for a ticker."""
    return f"filings for {ticker}"


@function_tool
def query_patent_db(company: str) -> str:
    """Search patent database."""
    return f"patents for {company}"


news_agent = Agent(
    name="news_researcher",
    instructions="Search the web for the last 90 days of news about the company and summarize risks.",
    tools=[WebSearchTool()],
    model="gpt-4o",
)
filings_agent = Agent(
    name="filings_researcher",
    instructions="Read the company's filings and extract going-concern and litigation disclosures.",
    tools=[query_sec_filings],
    model="gpt-4o",
)
patent_agent = Agent(
    name="patent_researcher",
    instructions="Review the patent portfolio and assess how defensible the core technology is.",
    tools=[query_patent_db],
    model="gpt-4o-mini",
)


async def research_company(name: str, ticker: str) -> list[str]:
    results = await asyncio.gather(
        Runner.run(news_agent, name),
        Runner.run(filings_agent, ticker),
        Runner.run(patent_agent, name),
    )
    return [r.final_output for r in results]
