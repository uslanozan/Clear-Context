"""Strict source-bound paragraph selections; these are not factual verdicts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NeedSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    need_id: str
    status: Literal["relevant", "not_found"]
    paragraph_ids: list[str]
    reason: str = Field(max_length=400)


class Selections(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    selections: list[NeedSelection]


class CoveredNeedSelection(NeedSelection):
    coverage: Literal["direct", "partial", "none"]
    missing_components: list[str] = Field(max_length=8)


class CoveredSelections(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    selections: list[CoveredNeedSelection]


def response_schema(contract: str) -> dict:
    if contract == "coverage_v2":
        return CoveredSelections.model_json_schema()
    if contract == "legacy_v1":
        return Selections.model_json_schema()
    raise ValueError("Unknown passage selection contract.")


def validate(content: str, allowed: dict[str, list[str]], contract: str = "legacy_v1"):
    response_schema(contract)
    model = CoveredSelections if contract == "coverage_v2" else Selections
    output = model.model_validate_json(content)
    if len(output.selections) != len(allowed) or {s.need_id for s in output.selections} != set(
        allowed
    ):
        raise ValueError("Every need must appear exactly once.")
    for selection in output.selections:
        if selection.status not in {"relevant", "not_found"}:
            raise ValueError("Invalid selection status.")
        ids = selection.paragraph_ids
        if len(ids) != len(set(ids)) or not set(ids) <= set(allowed[selection.need_id]):
            raise ValueError("Selection contains duplicate or unavailable paragraph IDs.")
        if (selection.status == "relevant") != bool(ids):
            raise ValueError("Status and selected paragraph list disagree.")
        if isinstance(selection, CoveredNeedSelection):
            if (selection.coverage == "none") != (selection.status == "not_found"):
                raise ValueError("Coverage and selected status disagree.")
            if selection.coverage == "partial" and not selection.missing_components:
                raise ValueError("Partial coverage must identify missing components.")
            if selection.coverage == "direct" and selection.missing_components:
                raise ValueError("Direct coverage cannot have missing components.")
            if any(not component.strip() for component in selection.missing_components):
                raise ValueError("Missing components cannot be blank.")
    return output
