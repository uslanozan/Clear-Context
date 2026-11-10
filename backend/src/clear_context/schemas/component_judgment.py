"""Evidence-bound component assessments with literal source positions."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from clear_context.schemas.evidence_judgment import JudgmentPacket, evidence_aliases


class ComponentReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    evidence_id: str
    relation: Literal["supports", "contradicts"]
    quote: str = Field(min_length=1)


class ComponentAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    description: str = Field(min_length=1)
    status: Literal["supported", "contradicted", "conflicting", "insufficient"]
    explanation: str = Field(min_length=1)
    evidence: list[ComponentReference]


class ComponentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    components: list[ComponentAssessment] = Field(min_length=1)


class AnchoredComponentAssessment(ComponentAssessment):
    # Exact claim wording this component evaluates, including any negation.
    claim_quote: str = Field(min_length=1)


class AnchoredComponentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    components: list[AnchoredComponentAssessment] = Field(min_length=1)


COMPONENT_CONTRACTS = {
    "components_v2": ComponentResponse,
    "components_v3": AnchoredComponentResponse,
}


def parent_claim(packet: JudgmentPacket) -> str:
    return next(c.statement for c in packet.claims if c.id == packet.needs[0].claim_id)


def locate_quote(text: str, quote: str) -> tuple[int, int] | None:
    """Start and end of the one place a cited quote occurs in a passage, or None.

    Pages keep non-breaking spaces and line breaks that a model writes as plain spaces, so
    runs of whitespace may differ; every other character must match. Reports show the
    page's own text at these positions, never the model's copy.
    """
    if text.count(quote) == 1:
        start = text.index(quote)
        return start, start + len(quote)
    words = quote.split()
    if not words:
        return None
    matches = list(re.finditer(r"\s+".join(map(re.escape, words)), text))
    if len(matches) != 1:
        return None
    return matches[0].start(), matches[0].end()


def validate_components(
    content: str, packet: JudgmentPacket, contract: str = "components_v2"
) -> tuple[ComponentResponse | AnchoredComponentResponse, list[dict]]:
    if len(packet.needs) != 1:
        raise ValueError("Component assessment requires exactly one research need.")
    response = COMPONENT_CONTRACTS[contract].model_validate_json(content)
    if contract == "components_v3":
        claim = parent_claim(packet)
        for component in response.components:
            if component.claim_quote not in claim:
                raise ValueError("Component claim_quote must be exact claim wording.")
    aliases = evidence_aliases(packet)
    evidence = {item.id: item for item in packet.evidence}
    citations = []
    for index, component in enumerate(response.components):
        relations = set()
        span_relations = {}
        for ref in component.evidence:
            if ref.evidence_id not in aliases:
                raise ValueError("Unknown evidence alias.")
            item = evidence[aliases[ref.evidence_id]]
            found = (
                locate_quote(item.quote, ref.quote) if item.need_id == packet.needs[0].id else None
            )
            if found is None:
                raise ValueError("Citation must uniquely match evidence for this need.")
            start, end = item.start + found[0], item.start + found[1]
            page_text = item.quote[found[0] : found[1]]
            # Reports keep one relation per cited span; the same words cannot both support
            # and contradict one component.
            span = (item.page_id, start, end)
            if span_relations.setdefault(span, ref.relation) != ref.relation:
                raise ValueError("The same excerpt cannot both support and contradict a component.")
            citations.append(
                {
                    "component_index": index,
                    "need_id": item.need_id,
                    "evidence_id": item.id,
                    "page_id": item.page_id,
                    "source_url": item.source_url,
                    "start": start,
                    "end": end,
                    "quote": page_text,
                    "relation": ref.relation,
                }
            )
            relations.add(ref.relation)
        required = {
            "supported": {"supports"},
            "contradicted": {"contradicts"},
            "conflicting": {"supports", "contradicts"},
            "insufficient": set(),
        }
        if relations != required[component.status]:
            raise ValueError("Evidence directions do not match the component status.")
    return response, citations
