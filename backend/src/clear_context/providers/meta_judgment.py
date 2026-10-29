"""Structured evidence-assessment request builder."""

import json

from clear_context.schemas.evidence_judgment import JudgmentPacket, response_model


def build_judgment_request(
    system: str,
    packet: JudgmentPacket,
    model: str,
    effort: str,
    tokens: int,
    response_contract: str = "legacy_v1",
):
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(packet.model_dump(), ensure_ascii=False)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "need_evidence_assessment",
                "strict": True,
                "schema": response_model(response_contract).model_json_schema(),
            },
        },
        "reasoning_effort": effort,
        "max_completion_tokens": tokens,
        "store": False,
        "stream": False,
    }
