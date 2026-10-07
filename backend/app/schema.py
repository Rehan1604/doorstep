import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class MissionRequest(BaseModel):
    minutes: int = Field(ge=5, le=120)
    energy: Literal["low", "medium", "high"] = "medium"
    interest: str = Field(default="anything", max_length=40)
    group: Literal["solo", "group"] = "solo"

    @field_validator("interest")
    @classmethod
    def clean_interest(cls, v: str) -> str:
        # Interest is interpolated into a prompt: keep letters, digits, spaces only.
        v = re.sub(r"[^A-Za-z0-9 ]", "", v).strip()
        return v or "anything"


class Mission(BaseModel):
    title: str = Field(min_length=3, max_length=80)
    duration_minutes: int = Field(ge=5, le=120)
    difficulty: Literal["easy", "moderate", "hard"]
    objective: str = Field(min_length=10, max_length=240)
    steps: list[str] = Field(min_length=2, max_length=6)
    why_it_matters: str = Field(min_length=5, max_length=240)
    safety_notes: list[str] = Field(min_length=1, max_length=4)


class Completion(BaseModel):
    completed: bool
    surprise: str = Field(default="", max_length=280)
    feeling: Literal["worse", "same", "better", "much_better"] = "better"


class Reflection(BaseModel):
    text: str = Field(min_length=5, max_length=300)
