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


class GroupAssignment(BaseModel):
    # null puts the investigation back in the ungrouped list.
    group_id: UUID | None = None
