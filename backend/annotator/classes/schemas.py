from pydantic import Field

from annotator.common.schemas import ApiModel


class ClassCreate(ApiModel):
    name: str
    detector_prompt: str = ""
    description: str = ""


class ClassUpdate(ApiModel):
    """Only the fields sent are changed. The index never changes."""

    name: str | None = None
    detector_prompt: str | None = None
    description: str | None = None


class ClassOut(ApiModel):
    index: int = Field(validation_alias="class_index")
    name: str
    detector_prompt: str
    description: str
