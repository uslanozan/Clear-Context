import json

import pytest

from clear_context.core.judges import load_judge
from clear_context.core.settings import PROJECT_ROOT
from clear_context.providers.meta_judgment import build_judgment_request
from clear_context.schemas.component_judgment import validate_components
from clear_context.schemas.evidence_judgment import EvidenceContext, JudgmentPacket
from clear_context.schemas.retrieval import ClaimReference, ResearchNeed


def packet():
    return JudgmentPacket(
        case_id="case",
        selection_ids=[],
        claims=[
            ClaimReference(
                id="c1", statement="The bridge opened in 2017.", quote="The bridge opened in 2017."
            )
        ],
        needs=[
            ResearchNeed(
                id="n1", claim_id="c1", description="The bridge opened in 2017.", status="planned"
            )
        ],
        evidence=[
            EvidenceContext(
                id="ev1",
                need_id="n1",
                selection_id="s1",
                paragraph_id="p1",
                page_id="page",
                source_id="source",
                source_url="https://example.org/bridge",
                fetched_at=0,
                reported_publication_dates=[],
                selected_start=30,
                selected_end=60,
                start=30,
                end=60,
                quote="The bridge opened in 2019.",
                before_truncated=False,
                after_truncated=False,
            )
        ],
    )


def response(quote="The bridge opened in 2019.", alias="E1", status="contradicted"):
    return json.dumps(
        {
            "components": [
                {
                    "description": "The bridge opened in 2017.",
                    "status": status,
                    "explanation": "The source reports a different date.",
                    "evidence": [{"evidence_id": alias, "relation": "contradicts", "quote": quote}],
                }
            ]
        }
    )


def test_component_citations_restore_source_id_and_offsets():
    result, citations = validate_components(response(), packet())
    assert result.components[0].status == "contradicted"
    assert citations[0]["evidence_id"] == "ev1"
    assert citations[0]["source_url"] == "https://example.org/bridge"
    assert (citations[0]["start"], citations[0]["end"]) == (30, 56)


@pytest.mark.parametrize(
    "content", [response(alias="E2"), response(quote="2018"), response(status="supported")]
)
def test_rejects_foreign_or_modified_citations_and_inconsistent_relation(content):
    with pytest.raises(ValueError):
        validate_components(content, packet())


def test_component_profile_builds_one_need_request():
    method, limits, system, contract = load_judge(
        PROJECT_ROOT / "config/judges.yaml",
        PROJECT_ROOT / "config/prompts.yaml",
        method="need_components_v2",
    )
    request = build_judgment_request(
        system, packet(), "muse-spark-1.3", limits.effort, limits.max_completion_tokens, contract
    )
    payload = json.loads(request["messages"][1]["content"])
    assert method == "need_components_v2"
    assert payload["evidence"][0]["id"] == "E1"
    assert payload["claim"] == "The bridge opened in 2017."


def anchored(claim_quote="The bridge opened in 2017."):
    value = json.loads(response())
    value["components"][0]["claim_quote"] = claim_quote
    return json.dumps(value)


def test_anchored_components_must_quote_the_claim_exactly():
    result, _ = validate_components(anchored(), packet(), "components_v3")
    assert result.components[0].claim_quote == "The bridge opened in 2017."
    with pytest.raises(ValueError, match="exact claim wording"):
        validate_components(anchored("The bridge did not open in 2017."), packet(), "components_v3")
    with pytest.raises(ValueError):
        validate_components(response(), packet(), "components_v3")


@pytest.mark.parametrize("profile", ["need_components_v3", "need_components_v4"])
def test_anchored_profile_sends_the_claim_and_the_need_as_focus(profile):
    neutral = packet().model_copy(
        update={
            "needs": [
                ResearchNeed(
                    id="n1",
                    claim_id="c1",
                    description="Whether the bridge opened in 2017",
                    status="planned",
                )
            ]
        }
    )
    method, limits, system, contract = load_judge(
        PROJECT_ROOT / "config/judges.yaml",
        PROJECT_ROOT / "config/prompts.yaml",
        method=profile,
    )
    request = build_judgment_request(
        system, neutral, "muse-spark-1.3", limits.effort, limits.max_completion_tokens, contract
    )
    payload = json.loads(request["messages"][1]["content"])
    assert contract == "components_v3"
    assert payload["claim"] == "The bridge opened in 2017."
    assert payload["focus"] == "Whether the bridge opened in 2017"
    assert "Keep the claim's polarity" in system
    schema = request["response_format"]["json_schema"]["schema"]
    assert "claim_quote" in json.dumps(schema)


def test_rejects_one_excerpt_cited_as_both_support_and_contradiction():
    # Observed live: "17 km east" cited both ways for "about 18 km northeast". The report
    # keeps one relation per excerpt, so this answer used to fail the whole investigation.
    content = json.dumps(
        {
            "components": [
                {
                    "description": "The bridge opened in 2017.",
                    "status": "conflicting",
                    "explanation": "Mixed.",
                    "evidence": [
                        {"evidence_id": "E1", "relation": "supports", "quote": "The bridge"},
                        {"evidence_id": "E1", "relation": "contradicts", "quote": "The bridge"},
                    ],
                }
            ]
        }
    )
    with pytest.raises(ValueError, match="both support and contradict"):
        validate_components(content, packet())


def packet_with_text(text):
    base = packet()
    evidence = base.evidence[0].model_copy(update={"quote": text, "end": 30 + len(text)})
    return base.model_copy(update={"evidence": [evidence]})


def test_citations_tolerate_page_whitespace_and_keep_the_page_text():
    # Pages keep non-breaking spaces and line breaks; models write plain spaces.
    page = "Record:\nThe bridge opened\nin 2019. Later works followed."
    _, citations = validate_components(response(), packet_with_text(page))
    citation = citations[0]
    assert citation["quote"] == "The bridge opened\nin 2019."
    assert page[citation["start"] - 30 : citation["end"] - 30] == citation["quote"]


@pytest.mark.parametrize(
    "page",
    [
        # Different words or punctuation are not whitespace.
        "The bridge was opened in 2019.",
        "The bridge opened in 2019",
        # Two places match, so the cited span is ambiguous.
        "The bridge opened in 2019. Again: The bridge opened in\n2019.",
    ],
)
def test_citations_still_reject_changed_or_ambiguous_quotes(page):
    with pytest.raises(ValueError):
        validate_components(response(), packet_with_text(page))
