"""Publication metadata is an explicit, unverified source of temporal context."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PublicationContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["missing", "unambiguous", "conflicting", "unparseable"] = "missing"
    normalized_dates: list[str] = Field(default_factory=list)
    unparsed_values: list[str] = Field(default_factory=list)
    origin: Literal["search_result_metadata"] = "search_result_metadata"
    verified: Literal[False] = False

    @model_validator(mode="after")
    def check_state(self):
        if len(self.normalized_dates) != len(set(self.normalized_dates)):
            raise ValueError("Publication dates must be unique.")
        for value in self.normalized_dates:
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError("Publication dates require ISO calendar dates.")
        size = len(self.normalized_dates)
        if self.status == "missing" and (size or self.unparsed_values):
            raise ValueError("Missing publication metadata cannot contain dates.")
        if self.status == "unambiguous" and (size != 1 or self.unparsed_values):
            raise ValueError("Unambiguous publication metadata needs one parsed date.")
        if self.status == "conflicting" and size < 2:
            raise ValueError("Conflicting publication metadata needs distinct dates.")
        if self.status == "unparseable" and (not self.unparsed_values or size > 1):
            raise ValueError("Unparseable publication metadata needs unresolved raw values.")
        return self
