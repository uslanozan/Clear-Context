from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GroupView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    position: int


class GroupName(BaseModel):
    name: str = Field(min_length=1, max_length=60)

    @field_validator("name")
    @classmethod
    def trimmed(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("A group needs a name.")
        return value


class InvestigationTitle(BaseModel):
    # null or an empty title shows the input text again.
    title: str | None = Field(default=None, max_length=120)

    @field_validator("title")
    @classmethod
    def trimmed(cls, value: str | None) -> str | None:
        value = " ".join((value or "").split())
        return value or None


class GroupAssignment(BaseModel):
    # null puts the investigation back in the ungrouped list.
    group_id: UUID | None = None
