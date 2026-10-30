"""Evidence-bound component assessments with literal source positions."""

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
        for ref in component.evidence:
            if ref.evidence_id not in aliases:
                raise ValueError("Unknown evidence alias.")
            item = evidence[aliases[ref.evidence_id]]
            if item.need_id != packet.needs[0].id or item.quote.count(ref.quote) != 1:
                raise ValueError("Citation must uniquely match evidence for this need.")
            start = item.start + item.quote.index(ref.quote)
            citations.append(
                {
                    "component_index": index,
                    "need_id": item.need_id,
                    "evidence_id": item.id,
                    "page_id": item.page_id,
                    "source_url": item.source_url,
                    "start": start,
                    "end": start + len(ref.quote),
                    "quote": ref.quote,
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
