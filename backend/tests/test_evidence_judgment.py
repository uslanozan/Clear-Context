"""Need-bound citations, insufficient evidence, caching and failure boundaries."""

import asyncio
import json

import httpx
import pytest

from clear_context.core.judges import load_judge
from clear_context.core.settings import PROJECT_ROOT, ModelSelection, Settings
from clear_context.providers.meta_structured import MetaStructuredProvider
from clear_context.repositories.judgment import JudgmentRepository
from clear_context.repositories.retrieval import RetrievalRepository, identity
from clear_context.schemas.evidence_judgment import (
    JudgmentResponse,
    need_status,
    resolved_citations,
    validate_judgment,
)
from clear_context.schemas.passage_selection import validate
from clear_context.schemas.retrieval import SavedResearchPlan
from clear_context.services.evidence_judgment import EvidenceJudgmentService, JudgmentJob
from clear_context.services.paragraphs import paragraphs
from clear_context.services.passage_context import source_context


@pytest.fixture
def saved(tmp_path):
    research = RetrievalRepository(tmp_path / "judge.sqlite")
    plan = SavedResearchPlan.model_validate(
        {
            "case_id": "case",
            "claims": [{"id": "C1", "statement": "Founded in 2002", "quote": "2002"}],
            "needs": [
                {"id": n, "claim_id": "C1", "description": description, "status": "planned"}
                for n, description in [("n1", "Founding year"), ("n2", "Urban adjacency")]
            ],
            "queries": [
                {
                    "id": "Q1",
                    "request": {"query": "history", "language": "en"},
                    "need_ids": ["n1", "n2"],
                }
            ],
        }
    )
    research.register_plan(plan)
    research.register_plan(plan.model_copy(update={"case_id": "other"}))
    research.ingest_search(
        "case",
        "Q1",
        {"query": "history", "results": [{"title": "A", "url": "https://example.org/a"}]},
        1000,
    )
    text = "Başlık\nThe university was founded in 2007.\nCenter distance is 8 km."
    page_id = research.save_page(identity("s_", "https://example.org/a"), text, 1000)
    units = paragraphs(text)
    selections = [
        dict(need_id=n, status="relevant", paragraph_ids=[p], reason="Candidate")
        for n, p in [("n1", "P002"), ("n2", "P003")]
    ]
    output = validate(json.dumps({"selections": selections}), {"n1": ["P002"], "n2": ["P003"]})
    windows = [source_context(text, units[i], n, 500, 500) for i, n in [(1, "n1"), (2, "n2")]]
    receipt = research.save_selection(
        "case",
        page_id,
        "full_page_v1",
        "model",
        "prompt",
        "key",
        output,
        {u.id: u for u in units},
        1000,
        context_windows=windows,
    )
    repo = JudgmentRepository(research)
    yield repo, JudgmentJob("case", ("n1", "n2"), (receipt,))
    research.close()


def response(packet):
    assessments = []
    for need in packet.needs:
        items = []
        for evidence in packet.evidence:
            if evidence.need_id != need.id:
                continue
            directional = need.id == "n1"
            items.append(
                {
                    "evidence_id": evidence.id,
                    "relation": "contradicts" if directional else "insufficient",
                    "coverage": "complete" if directional else "none",
                    "explanation": "Recorded source",
                    "excerpts": [{"quote": evidence.quote}] if directional else [],
                }
            )
        assessments.append(
            {
                "need_id": need.id,
                "evidence_assessments": items,
                "missing_information": [] if need.id == "n1" else ["Urban boundary information"],
                "explanation": "Assessment limited to supplied sources",
            }
        )
    return {"assessments": assessments}


def service(repo, handler, **changes):
    method, limits, system, contract = load_judge(
        PROJECT_ROOT / "config/judges.yaml",
        PROJECT_ROOT / "config/prompts.yaml",
        method="need_evidence_v1",
    )
    provider = MetaStructuredProvider(
        Settings(
            _env_file=None, app_mode="meta", allow_paid_api_calls=True, meta_api_key="fake-secret"
        ),
        httpx.MockTransport(handler),
    )
    return EvidenceJudgmentService(
        repo,
        provider,
        method,
        limits.model_copy(update=changes),
        system,
        ModelSelection(alias="spark_1_3", api_model_id="muse-spark-1.3", training_use=False),
        clock=lambda: 1000,
        response_contract=contract,
    )


def completion(value):
    return httpx.Response(
        200,
        json={
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(value)}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 20},
        },
    )


def test_valid_citations_resolve_absolute_unicode_offsets(saved):
    repo, job = saved
    packet = repo.packet(job.case_id, job.need_ids, job.selection_ids)
    result = validate_judgment(json.dumps(response(packet)), packet)
    assert [need_status(a) for a in result.assessments] == ["contradicted", "insufficient"]
    citation = resolved_citations(result, packet)[0]
    page = repo.research.page(citation["page_id"])
    assert page["content"][citation["start"] : citation["end"]] == citation["quote"]
    assert packet.source_reliability_assessed is False


@pytest.mark.parametrize("fault", ["wrong_quote", "cross_need", "missing_need", "missing_evidence"])
def test_invalid_citations_and_bindings_are_rejected(saved, fault):
    repo, job = saved
    packet = repo.packet(job.case_id, job.need_ids, job.selection_ids)
    value = response(packet)
    if fault == "wrong_quote":
        value["assessments"][0]["evidence_assessments"][0]["excerpts"][0]["quote"] = (
            "Founded in 2002"
        )
    if fault == "cross_need":
        value["assessments"][0]["evidence_assessments"][0]["evidence_id"] = packet.evidence[-1].id
    if fault == "missing_need":
        value["assessments"].pop()
    if fault == "missing_evidence":
        value["assessments"][0]["evidence_assessments"] = []
    with pytest.raises(ValueError):
        validate_judgment(json.dumps(value), packet)


def test_partial_support_stays_insufficient_and_conflict_is_preserved(saved):
    repo, job = saved
    packet = repo.packet(job.case_id, job.need_ids, job.selection_ids)
    value = response(packet)
    assessment = value["assessments"][0]
    item = assessment["evidence_assessments"][0]
    item.update(relation="supports", coverage="partial")
    assessment["missing_information"] = ["Reference period"]
    assert need_status(JudgmentResponse.model_validate(value).assessments[0]) == "insufficient"
    second = dict(item)
    second["relation"] = "contradicts"
    assessment["evidence_assessments"].append(second)
    assert need_status(JudgmentResponse.model_validate(value).assessments[0]) == "mixed"


def test_other_case_receipts_are_rejected_before_network(saved):
    repo, job = saved
    runner = service(repo, lambda _: pytest.fail("No request expected"))
    with pytest.raises(ValueError):
        asyncio.run(runner.assess([job, JudgmentJob("other", ("n1",), job.selection_ids)]))
    assert runner.calls == 0


def test_no_evidence_needs_are_insufficient_without_a_model_call(saved):
    repo, job = saved
    runner = service(repo, lambda _: pytest.fail("No request expected"))
    row = asyncio.run(runner.assess([JudgmentJob("case", ("n2",), ())]))[0]
    assert runner.calls == 0 and row["result"]["assessments"][0]["status"] == "insufficient"
    assert row["result"]["claim_verdicts"] is None


def test_successful_assessment_is_persisted_and_cache_replay_is_free(saved):
    repo, job = saved
    packet = repo.packet(job.case_id, job.need_ids, job.selection_ids)
    runner = service(repo, lambda _: completion(response(packet)))
    first = asyncio.run(runner.assess([job]))[0]
    replay = service(repo, lambda _: pytest.fail("No new call"), max_model_calls=0)
    second = asyncio.run(replay.assess([job]))[0]
    assert first["status"] == "assessed" and second["cached"] and replay.calls == 0
    assert first["judgment_id"] == second["judgment_id"]
    assert len(repo.export()["research_judgments"]) == 1
    assert "fake-secret" not in json.dumps(repo.export())


def test_bad_model_quote_is_failure_not_an_insufficient_verdict(saved):
    repo, job = saved
    packet = repo.packet(job.case_id, job.need_ids, job.selection_ids)
    value = response(packet)
    value["assessments"][0]["evidence_assessments"][0]["excerpts"][0]["quote"] = "Fabricated"
    runner = service(repo, lambda _: completion(value))
    row = asyncio.run(runner.assess([job]))[0]
    assert row["status"] == "invalid_judgment" and "result" not in row
    assert not repo.export()["research_judgments"]
    assert repo.research.cached("judgment", row["request_key"], 1000) is None


def test_rate_failure_stops_queued_jobs_without_retry(saved):
    repo, job = saved
    runner = service(repo, lambda _: httpx.Response(429, json={"error": "rate"}), max_concurrency=1)
    rows = asyncio.run(runner.assess([job, job]))
    assert runner.calls == 1
    assert [r["status"] for r in rows] == ["rate_limited", "not_run_after_failure"]


def test_oversized_input_rejected_without_truncation_or_calls(saved):
    repo, job = saved
    runner = service(repo, lambda _: pytest.fail("No request"), max_input_chars=10)
    with pytest.raises(ValueError):
        runner.prepare(job)
    assert runner.calls == 0


def reconciled_response(packet):
    value = response(packet)
    for assessment in value["assessments"]:
        ids = [
            x["evidence_id"]
            for x in assessment["evidence_assessments"]
            if x["relation"] != "insufficient"
        ]
        assessment.update(
            coverage_summary={
                "coverage": "complete" if ids else "none",
                "evidence_ids": ids,
                "explanation": "Reconciled across all supplied evidence.",
            },
            time_basis={
                "mode": "explicit_source_text" if ids else "not_required",
                "evidence_ids": ids,
                "explanation": "Source text dates the event." if ids else "No period needed.",
            },
        )
    return value


def test_reconciled_need_cannot_keep_gaps_already_claimed_complete(saved):
    repo, job = saved
    packet = repo.packet(job.case_id, job.need_ids, job.selection_ids)
    value = reconciled_response(packet)
    validate_judgment(json.dumps(value), packet, "reconciled_v1_1")
    value["assessments"][0]["missing_information"] = ["A weaker excerpt lacks the year"]
    with pytest.raises(ValueError, match="Complete need coverage"):
        validate_judgment(json.dumps(value), packet, "reconciled_v1_1")


def test_publication_basis_requires_unambiguous_metadata_and_same_need(saved):
    from clear_context.schemas.source_time import PublicationContext

    repo, job = saved
    packet = repo.packet(job.case_id, job.need_ids, job.selection_ids)
    value = reconciled_response(packet)
    basis = value["assessments"][0]["time_basis"]
    basis["mode"] = "publication_context"
    with pytest.raises(ValueError, match="publication dates"):
        validate_judgment(json.dumps(value), packet, "reconciled_v1_1")
    packet = packet.model_copy(
        update={
            "evidence": [
                e.model_copy(
                    update={
                        "publication_context": PublicationContext(
                            status="unambiguous", normalized_dates=["2023-10-26"]
                        )
                    }
                )
                for e in packet.evidence
            ]
        }
    )
    validate_judgment(json.dumps(value), packet, "reconciled_v1_1")
    basis["evidence_ids"] = [packet.evidence[-1].id]
    with pytest.raises(ValueError, match="in this need"):
        validate_judgment(json.dumps(value), packet, "reconciled_v1_1")


def test_joint_partial_evidence_can_complete_a_need_without_individual_complete(saved):
    repo, job = saved
    packet = repo.packet(job.case_id, ("n1",), job.selection_ids)
    first_text = "The artifact was made in 2007."
    first = packet.evidence[0].model_copy(
        update={
            "quote": first_text,
            "start": 0,
            "end": len(first_text),
            "selected_start": 0,
            "selected_end": len(first_text),
        }
    )
    second = first.model_copy(
        update={"id": "ev_second", "quote": "It is ceramic.", "start": 100, "end": 114}
    )
    packet = packet.model_copy(
        update={
            "claims": [
                packet.claims[0].model_copy(
                    update={
                        "statement": "The artifact is ceramic and was made in 2007.",
                        "quote": "ceramic and made in 2007",
                    }
                )
            ],
            "needs": [
                packet.needs[0].model_copy(update={"description": "Artifact material and year"})
            ],
            "evidence": [first, second],
        }
    )
    items = [
        {
            "evidence_id": e.id,
            "relation": "supports",
            "coverage": "partial",
            "explanation": "One component only.",
            "excerpts": [{"quote": e.quote}],
        }
        for e in packet.evidence
    ]
    value = {
        "assessments": [
            {
                "need_id": "n1",
                "evidence_assessments": items,
                "missing_information": [],
                "explanation": "Together the components are supplied.",
                "coverage_summary": {
                    "coverage": "complete",
                    "evidence_ids": [e.id for e in packet.evidence],
                    "explanation": "Both components are available.",
                },
                "time_basis": {
                    "mode": "explicit_source_text",
                    "evidence_ids": [first.id],
                    "explanation": "Date is in source text.",
                },
            }
        ]
    }
    result = validate_judgment(json.dumps(value), packet, "reconciled_v1_1")
    assert need_status(result.assessments[0]) == "supported"


def test_new_contract_no_evidence_remains_free_and_schema_complete(saved):
    repo, job = saved
    runner = service(repo, lambda _: pytest.fail("No new call"))
    runner.response_contract = "reconciled_v1_1"
    row = asyncio.run(runner.assess([JudgmentJob("case", ("n2",), ())]))[0]
    assert runner.calls == 0 and row["result"]["assessments"][0]["status"] == "insufficient"
    assert row["result"]["assessments"][0]["coverage_summary"]["coverage"] == "none"


def test_new_contract_summary_and_time_survive_cache_replay(saved):
    repo, job = saved
    packet = repo.packet(job.case_id, job.need_ids, job.selection_ids)
    value = reconciled_response(packet)
    method, limits, system, contract = load_judge(
        PROJECT_ROOT / "config/judges.yaml",
        PROJECT_ROOT / "config/prompts.yaml",
        method="need_evidence_v1_1",
    )

    def handler(request):
        payload = json.loads(request.content)
        assert "coverage_summary" in json.dumps(payload["response_format"])
        assert "publication_context" in payload["messages"][1]["content"]
        return completion(value)

    runner = service(repo, handler)
    runner.method, runner.system, runner.response_contract = method, system, contract
    first = asyncio.run(runner.assess([job]))[0]
    runner.limits = limits.model_copy(update={"max_model_calls": 0})
    second = asyncio.run(runner.assess([job]))[0]
    assert second["cached"] and runner.calls == 1
    assert first["judgment_id"] == second["judgment_id"]
    assert first["result"]["assessments"][0]["coverage_summary"]["coverage"] == "complete"
    assert first["result"]["assessments"][0]["time_basis"]["mode"] == "explicit_source_text"
