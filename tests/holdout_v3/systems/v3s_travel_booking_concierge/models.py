from typing import Literal

from pydantic import BaseModel


class RefundDecision(BaseModel):
    outcome: Literal["full_refund", "partial_refund", "no_refund"]
    reason: str


class PassportData(BaseModel):
    surname: str
    given_names: str
    passport_number: str
    nationality: str
    birth_date: str
    expiry_date: str


class RiskNote(BaseModel):
    level: Literal["low", "medium", "high"]
    summary: str
    precautions: list[str]


class SentimentTag(BaseModel):
    label: Literal["positive", "neutral", "negative"]
