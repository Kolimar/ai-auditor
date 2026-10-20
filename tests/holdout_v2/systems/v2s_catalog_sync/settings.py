from enum import Enum

MODEL_TEXT = "gpt-4o"
MODEL_FAST = "gpt-4o-mini"
MODEL_GEMINI = "gemini-2.5-pro"
MODEL_GEMINI_VISION = "gemini-2.5-flash"

FX_TO_EUR = {"USD": 0.92, "GBP": 1.17, "JPY": 0.0061}


class Category(str, Enum):
    KITCHEN = "kitchen"
    GARDEN = "garden"
    TOYS = "toys"
    LIGHTING = "lighting"
    PET = "pet supplies"
    OFFICE = "office"
    SPORT = "sport"
    BEAUTY = "beauty"
    TOOLS = "tools"
    AUDIO = "audio"
    BAGS = "bags"
    BABY = "baby"


def label_for(category: Category) -> str:
    return category.value
