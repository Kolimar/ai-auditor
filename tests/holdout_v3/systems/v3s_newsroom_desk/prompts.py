METADATA_PROMPT = """Below is a NewsML-G2 item from the wire service. Pull out the
guid, the urgency (1-8), the slugline, the dateline city and the embargo timestamp,
and answer with a JSON object using those five keys."""

CMS_CHECK_PROMPT = """You get an article record headed for the CMS. Make sure that all of
slug, headline, byline, body and section are present, that none of them is an empty string,
and that word_count is a positive integer. Say VALID, or INVALID followed by what is wrong."""

DIGEST_PROMPT = """Turn the JSON list of stories below into a Markdown digest.
One bullet per story, formatted as: - **{headline}** ({section}) - {slug}
Keep the original order."""

SUMMARY_PROMPT = """Write a three-sentence summary of this wire story for the morning briefing.
Stay neutral, keep attributions ("police said", "the ministry claims") and do not add context that
the story itself does not give."""

HEADLINE_PROMPT = """You are a copy chief with fifteen years on a metro desk.
Suggest five headline options for the story, each under 70 characters.
Vary the angle: one straight news, one human-interest, one explanatory, one question, one number-led.
Avoid clickbait and avoid the passive voice when possible."""

FACTCHECK_PROMPT = """Check every factual claim in the draft against the source excerpts supplied.
For each claim output SUPPORTED, CONTRADICTED or UNVERIFIABLE, cite the excerpt that decides it, and
list quotes that are not found verbatim in the sources."""

BACKGROUND_PROMPT = """You are researching background for a reporter.
Think about what else the reporter should know about the story's topic, give a
paragraph of context, and then say either CONTINUE (if more angles remain) or DONE."""

EDITOR_CHAT_SYSTEM = (
    "You are the assistant of the night editor. Answer questions about style rules, "
    "libel risks and sourcing practice. Be brief."
)
