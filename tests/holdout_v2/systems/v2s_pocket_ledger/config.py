from dataclasses import dataclass

CATEGORIES = ("groceries", "dining", "transport", "rent", "utilities", "entertainment", "health", "other")


@dataclass(frozen=True)
class ModelNames:
    big: str = "gpt-4o"
    small: str = "gpt-4o-mini"


MODELS = ModelNames()

SYSTEM_CATEGORIZER = (
    "You label card transactions. The memo text is raw bank output, e.g. 'POS DEBIT 4417 TRADER JOES #552 "
    "OAKLAND CA'. Pick the best matching category from the allowed list and return just that word."
)

SYSTEM_ADVISOR = (
    "You are a thoughtful money coach. Look at the user's situation and goals and suggest realistic "
    "adjustments to their budget. Be honest about trade-offs and avoid generic platitudes."
)
