"""Meta structured paragraph selection with explicit live-call authorization."""

import json

from clear_context.providers.meta_structured import MetaStructuredProvider
from clear_context.providers.meta_structured import ModelResponseFailure as SelectionFailure
from clear_context.schemas.passage_selection import response_schema
from clear_context.services.paragraphs import Paragraph


def build_selection_request(
    system: str,
    page: dict,
    needs: list[dict],
    claims: list[dict],
    items: list[Paragraph],
    allowed: dict[str, list[str]],
    *,
    model: str = "muse-spark-1.3",
    effort: str = "low",
    max_completion_tokens: int = 4096,
    response_contract: str = "legacy_v1",
) -> dict:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "source_url": page["url"],
                        "needs": needs,
                        "claims": claims,
                        "allowed_paragraph_ids_by_need": allowed,
                        "paragraphs": [{"id": p.id, "text": p.text} for p in items],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "passage_selection",
                "strict": True,
                "schema": response_schema(response_contract),
            },
        },
        "reasoning_effort": effort,
        "max_completion_tokens": max_completion_tokens,
        "store": False,
        "stream": False,
    }


__all__ = ["MetaPassageProvider", "SelectionFailure", "build_selection_request"]


class MetaPassageProvider(MetaStructuredProvider):
    async def select(self, payload: dict, timeout: float) -> dict:
        return await self.complete(payload, timeout)
