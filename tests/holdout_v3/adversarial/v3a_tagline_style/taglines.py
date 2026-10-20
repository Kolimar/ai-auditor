from pydantic_ai import Agent

tagline_writer = Agent(
    "openai:gpt-4o",
    system_prompt=(
        "You write short, witty taglines for craft beer labels. Use the brewer's notes. "
        "Do not copy the examples; they only show the range of voice we like.\n\n"
        "Notes: smoky porter, brewed near a quarry -> 'Dark as the pit, kind as the pub.'\n"
        "Notes: citrus session ale, summer -> 'Sunday afternoon, bottled.'\n"
        "Notes: barrel aged stout, 11% -> 'Sip it like it owes you nothing.'\n"
        "Notes: wheat beer, bakery next door -> 'Rises to the occasion.'"
    ),
)


async def write_tagline(notes: str) -> str:
    result = await tagline_writer.run(notes)
    return result.output
