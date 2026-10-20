from agents import Agent, Runner, WebSearchTool, CodeInterpreterTool

literature_scout = Agent(
    name="LiteratureScout",
    instructions=(
        "Search the web and preprint servers for papers on the assigned gene. Read many abstracts and return "
        "only a ranked list of at most ten relevant papers with one-line relevance notes."
    ),
    tools=[WebSearchTool()],
    model="gpt-4o-mini",
)

stats_runner = Agent(
    name="StatsRunner",
    instructions=(
        "Run the statistical re-analysis of the supplied cohort table in the sandbox and report effect sizes "
        "with confidence intervals."
    ),
    tools=[CodeInterpreterTool()],
    model="gpt-4o",
)

trial_lead = Agent(
    name="TrialLead",
    instructions=(
        "You prepare a briefing on a gene's association with trial outcomes. Use LiteratureScout and StatsRunner "
        "in parallel, reconcile their findings, flag disagreements with published effect sizes and write the briefing."
    ),
    tools=[
        literature_scout.as_tool(tool_name="scout", tool_description="Find relevant papers"),
        stats_runner.as_tool(tool_name="restat", tool_description="Re-run cohort statistics"),
    ],
    model="gpt-4o",
)


async def brief(gene: str, cohort_csv: str) -> str:
    result = await Runner.run(trial_lead, f"Gene: {gene}\nCohort data:\n{cohort_csv}")
    return result.final_output
