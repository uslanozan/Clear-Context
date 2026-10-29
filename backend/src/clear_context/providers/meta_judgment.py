"""Structured evidence-assessment request builder."""

import json
from copy import deepcopy

from clear_context.schemas.evidence_judgment import (
    JudgmentPacket,
    evidence_aliases,
    response_model,
)


def compact_input(packet: JudgmentPacket) -> dict:
    value = packet.model_dump()
    aliases = {identity: alias for alias, identity in evidence_aliases(packet).items()}
    fields = (
        "need_id",
        "source_url",
        "reported_publication_dates",
        "publication_context",
        "quote",
        "before_truncated",
        "after_truncated",
    )
    return {
        "claims": value["claims"],
        "needs": value["needs"],
        "evidence": [
            {"id": aliases[e["id"]], **{field: e[field] for field in fields}}
            for e in value["evidence"]
        ],
        "source_reliability_assessed": False,
    }


def compact_schema(packet: JudgmentPacket) -> dict:
    """Constrain references and evidence counts separately for each requested need."""
    schema = response_model("compact_v1_2").model_json_schema()
    definitions = schema["$defs"]
    aliases = evidence_aliases(packet)
    variants = []
    for need in packet.needs:
        allowed = [
            alias
            for alias, identity in aliases.items()
            if any(e.id == identity and e.need_id == need.id for e in packet.evidence)
        ]
        variant = deepcopy(definitions["CompactNeedAssessment"])
        properties = variant["properties"]
        properties["need_id"] = {"type": "string", "enum": [need.id]}
        item = deepcopy(definitions["CompactEvidenceAssessment"])
        if allowed:
            item["properties"]["evidence_id"] = {"type": "string", "enum": allowed}
        properties["evidence_assessments"] = {
            "type": "array",
            "items": item,
            "minItems": len(allowed),
            "maxItems": len(allowed),
        }
        for field, definition in [
            ("coverage_summary", "CompactCoverageSummary"),
            ("time_basis", "CompactTemporalBasis"),
        ]:
            summary = deepcopy(definitions[definition])
            summary["properties"]["evidence_ids"] = {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": len(allowed),
            }
            if allowed:
                summary["properties"]["evidence_ids"]["items"]["enum"] = allowed
            properties[field] = summary
        variants.append(variant)
    schema["properties"]["assessments"] = {
        "type": "array",
        "items": {"anyOf": variants},
        "minItems": len(packet.needs),
        "maxItems": len(packet.needs),
    }
    return schema


def build_judgment_request(
    system: str,
    packet: JudgmentPacket,
    model: str,
    effort: str,
    tokens: int,
    response_contract: str = "legacy_v1",
):
    compact = response_contract == "compact_v1_2"
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    compact_input(packet) if compact else packet.model_dump(), ensure_ascii=False
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "need_evidence_assessment",
                "strict": True,
                "schema": compact_schema(packet)
                if compact
                else response_model(response_contract).model_json_schema(),
            },
        },
        "reasoning_effort": effort,
        "max_completion_tokens": tokens,
        "store": False,
        "stream": False,
    }
