"""Human-readable judgment vocabulary, checked against the executable contract."""

from pathlib import Path
from typing import Literal, get_args

import yaml
from pydantic import BaseModel, ConfigDict, Field

from clear_context.schemas.evidence_judgment import (
    ConflictType,
    EvidenceBasis,
    EvidenceCoverage,
    EvidenceRelation,
    EvidenceRelevance,
    JudgmentExecutionStatus,
    NeedStatus,
)


class LabelDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class JudgmentLabelCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1]
    scope: Literal["provided_evidence_only"]
    groups: dict[str, dict[str, LabelDefinition]]


def load_judgment_labels(path: Path) -> JudgmentLabelCatalog:
    catalog = JudgmentLabelCatalog.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    )
    expected = {
        "evidence_relation": set(get_args(EvidenceRelation)),
        "evidence_coverage": set(get_args(EvidenceCoverage)),
        "need_status": set(get_args(NeedStatus)),
        "execution_status": set(get_args(JudgmentExecutionStatus)),
        "evidence_relevance": set(get_args(EvidenceRelevance)),
        "evidence_basis": set(get_args(EvidenceBasis)),
        "conflict_type": set(get_args(ConflictType)),
    }
    if set(catalog.groups) != set(expected):
        raise ValueError("Judgment label groups do not match the executable contract.")
    for group, keys in expected.items():
        if set(catalog.groups[group]) != keys:
            raise ValueError(f"Judgment label keys do not match the {group} contract.")
    return catalog
