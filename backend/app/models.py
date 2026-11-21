import json
from pathlib import Path

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

HOLD_REASONS = json.loads(Path(__file__).with_name("hold_reasons.json").read_text(encoding="utf-8"))

Text = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16000)
]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
Category = Literal[
    "fraud", "harassment", "corruption", "safety", "discrimination", "other"
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Identity(Strict):
    kind: Literal["reporter", "person"]
    aliases: list[Name] = Field(min_length=1, max_length=8)


class Report(Strict):
    text: Text
    reporter_mode: Literal["anonymous", "confidential"] = "anonymous"
    source: Literal["text"] = "text"
    identities: list[Identity] = Field(default_factory=list, max_length=32)


class Decision(Strict):
    policy: Literal["P1", "P2", "P3", "P4", "P5", "P6"]
    action: Literal["PROTECT", "ALLOW", "BLOCK", "LOCAL_ONLY", "HUMAN_ONLY"]
    count: int | None = Field(ge=0)


class DraftQuestions(Strict):
    missing: list[Literal["what", "when", "where", "who", "evidence"]]
    follow_up: list[str]


class Brief(Strict):
    facts: list[str]
    timeline: list[str]
    evidence: list[str]


class Case(Strict):
    case_id: str
    reporter: Literal["REPORTER_01"] = "REPORTER_01"
    category: Category
    summary: str
    persons: list[str]
    received_at: str
    decisions: list[Decision]
    brane_status: Literal["ok"] = "ok"
    brief: Brief | None = None


class HeldCase(Strict):
    case_id: Annotated[str, StringConstraints(pattern=r"^WB-[0-9a-f]{32}$")]
    reporter: Literal["REPORTER_01"] = "REPORTER_01"
    status: Literal["held_for_review", "held_unverified"]
    hold_reason: str
    policy: Literal["P1", "P2", "P3", "P4", "P5"]
    received_at: str
    decisions: list[Decision]

    @model_validator(mode="after")
    def validate_hold(self):
        if self.hold_reason not in HOLD_REASONS:
            raise ValueError("Unknown hold reason")
        return self


class Extraction(Strict):
    category: Category
    summary: str
    approximate_time: str
    location: str
    persons: list[str]
    evidence: list[str]
    missing: list[str]
    follow_up: list[str]


class Message(Strict):
    role: Literal["user", "assistant", "system"]
    content: Text


class SessionRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID


class StreamOptions(BaseModel):
    # Sent by ElevenLabs' Custom LLM caller ({"include_usage": true}); accepted, never acted on.
    model_config = ConfigDict(extra="ignore", strict=True)
    include_usage: bool | None = None


class Chat(Strict):
    model: str
    messages: list[Message] = Field(min_length=1, max_length=64)
    elevenlabs_extra_body: SessionRef
    stream: Literal[True] = True
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=16000)
    max_completion_tokens: int | None = Field(default=None, ge=1, le=16000)
    stream_options: StreamOptions | None = None
    top_p: float | None = Field(default=None, ge=0, le=1)
    user: Name | None = None
    user_id: Name | None = None
    tool_choice: Literal["none"] | None = None
    tools: list | None = Field(default=None, max_length=0)

    @model_validator(mode="after")
    def check_history(self):
        if (
            self.messages[-1].role != "user"
            or sum(len(m.content) for m in self.messages) > 16000
        ):
            raise ValueError("Invalid conversation history")
        return self


class Confirm(Strict):
    confirmed: bool
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def require_confirmation(self):
        if not self.confirmed:
            raise ValueError("Explicit confirmation required")
        return self
