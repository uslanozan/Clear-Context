"""Find claims that state the same fact, so each fact is researched once.

Speakers repeat themselves ("we received no test kits", "no such aid reached us"); without
grouping, each wording gets its own searches and judgments. One model call groups them; the
first claim of a group in text order is researched and the others point to it. Any failure
keeps every claim separate, so grouping never removes research by mistake of its own.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from clear_context.domain.investigation import ModelUsage
from clear_context.providers.meta_structured import ModelResponseFailure

PROMPT_VERSION = "claim_grouping_v1"
# Fewer claims rarely repeat each other; the call is skipped.
MIN_CLAIMS = 3


@dataclass(frozen=True)
class Grouping:
    # duplicate claim ID -> the claim ID that is researched in its place
    duplicates: dict[str, str]
    usage: ModelUsage | None = None
    failed: bool = False


def build_request(claims: list[tuple[str, str]], model: str, prompts_path: Path) -> dict:
    catalog = yaml.safe_load(prompts_path.read_text(encoding="utf-8-sig"))
    ids = [claim_id for claim_id, _ in claims]
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": catalog["experiments"][PROMPT_VERSION]["system"]},
            {
                "role": "user",
                "content": json.dumps(
                    {"claims": [{"id": i, "text": t} for i, t in claims]}, ensure_ascii=False
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "claim_groups",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "groups": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "claim_ids": {
                                        "type": "array",
                                        "items": {"type": "string", "enum": ids},
                                    }
                                },
                                "required": ["claim_ids"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["groups"],
                    "additionalProperties": False,
                },
            },
        },
        "reasoning_effort": "low",
        "max_completion_tokens": 4096,
        "store": False,
        "stream": False,
    }


def parse_groups(content: str, order: list[str]) -> dict[str, str]:
    """Duplicate -> kept claim. Invalid answers raise ValueError: unknown IDs, a claim in two
    groups, or a group of fewer than two claims."""
    groups = json.loads(content)["groups"]
    position = {claim_id: index for index, claim_id in enumerate(order)}
    seen, duplicates = set(), {}
    for group in groups:
        ids = list(dict.fromkeys(group["claim_ids"]))
        if len(ids) < 2 or any(i not in position for i in ids) or seen & set(ids):
            raise ValueError("Invalid claim group.")
        seen |= set(ids)
        ids.sort(key=position.get)
        duplicates.update({claim_id: ids[0] for claim_id in ids[1:]})
    return duplicates


async def group_claims(claims, provider, model: str, prompts_path: Path) -> Grouping:
    """claims: (id, statement) pairs in text order."""
    if len(claims) < MIN_CLAIMS or provider is None:
        return Grouping({})
    try:
        body = await provider.complete(build_request(claims, model, prompts_path), 60)
    except (ModelResponseFailure, OSError, ValueError):
        return Grouping({}, failed=True)
    usage = body.get("usage") or {} if isinstance(body, dict) else {}
    record = ModelUsage(
        task="claim_grouping",
        model_id=model,
        prompt_version=PROMPT_VERSION,
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
    )
    try:
        duplicates = parse_groups(
            body["choices"][0]["message"]["content"], [claim_id for claim_id, _ in claims]
        )
    except (KeyError, IndexError, TypeError, ValueError):
        return Grouping({}, record, failed=True)
    return Grouping(duplicates, record)
