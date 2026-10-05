import json
from pathlib import Path
from typing import Literal

from ollama import RequestError, ResponseError, chat
from pydantic import BaseModel


INSTRUCTIONS_FILE = Path(__file__).with_name("ai_instructions.txt")


class AIAnalysisError(Exception):
    pass


class ChangeAnalysis(BaseModel):
    summary: str
    category: Literal[
        "Pricing", "Product", "Positioning", "Hiring", "Leadership", "Other"
    ]
    importance: Literal["Low", "Medium", "High"]
    why_it_matters: str
    confidence: Literal["Low", "Medium", "High"]


def analyze_change(event):
    instructions = INSTRUCTIONS_FILE.read_text(encoding="utf-8")

    try:
        response = chat(
            model="qwen3:8b",
            messages=[
                {"role": "system", "content": instructions},
                {
                    "role": "user",
                    "content": json.dumps(event, indent=2),
                },
            ],
            think=False,
            format=ChangeAnalysis.model_json_schema(),
            options={"temperature": 0},
        )
        analysis = ChangeAnalysis.model_validate_json(response.message.content)
    except (RequestError, ResponseError, ValueError) as error:
        raise AIAnalysisError("The AI analysis request could not be completed.") from error

    return analysis.model_dump()
