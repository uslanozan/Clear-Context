"""Bind saved query plans without changing original claims or queries."""

from clear_context.schemas.retrieval import (
    ENDPOINT,
    SearchRequest,
    SearchResponse,
    SearchResult,
    canonical_source_url,
    parse_response,
)

__all__ = [
    "ENDPOINT",
    "SearchRequest",
    "SearchResult",
    "SearchResponse",
    "canonical_source_url",
    "parse_response",
    "bind_plan_queries",
    "deduplicate_jobs",
]


def bind_plan_queries(case_id: str, plan: dict) -> list[dict]:
    needs = {item["id"]: item for item in plan["needs"]}
    jobs = []
    for question in plan["questions"]:
        for query in question["queries"]:
            ids = query["need_ids"]
            if (
                not ids
                or len(set(ids)) != len(ids)
                or any(item not in needs for item in ids)
            ):
                raise ValueError("Query has missing, unknown or duplicate need IDs.")
            if any(needs[item]["status"] != "planned" for item in ids):
                raise ValueError("A search query references a deferred need.")
            jobs.append(
                {
                    "request": SearchRequest(
                        query=query["text"], language=query["language"]
                    ),
                    "binding": {
                        "plan_case_id": case_id,
                        "need_ids": ids,
                        "claim_ids": sorted({needs[item]["claim_id"] for item in ids}),
                        "question": question["question"],
                    },
                }
            )
    return jobs


def deduplicate_jobs(jobs: list[dict]) -> list[dict]:
    unique = {}
    for job in jobs:
        request = job["request"]
        key = request.cache_key
        if key not in unique:
            unique[key] = {
                "cache_key": key,
                "request": request.model_dump(),
                "bindings": [],
            }
        binding = job["binding"]
        if binding not in unique[key]["bindings"]:
            unique[key]["bindings"].append(binding)
    return list(unique.values())
