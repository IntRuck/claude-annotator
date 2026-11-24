from datetime import datetime

from annotator.common.schemas import ApiModel


class EngineState(ApiModel):
    label: str
    ready: bool          # can it run right now (e.g. a Gemini key is set)?
    note: str            # why not, or a warning, in plain words
    models: list[str]    # models the worker found (Gemini: what the key can use)
    supports_refine: bool


class EnginePauseOut(ApiModel):
    engine: str
    label: str
    reason: str
    paused_at: datetime


class EngineStatus(ApiModel):
    worker_online: bool
    last_seen_at: datetime | None
    engines: dict[str, EngineState]
    paused: list[EnginePauseOut]


class ResumeResult(ApiModel):
    resumed: list[str]
