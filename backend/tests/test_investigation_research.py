import json
from uuid import UUID, uuid4

from clear_context.core.settings import ModelSelection, Settings
from clear_context.db.base import Base
from clear_context.db.session import create_database, create_session_factory
from clear_context.domain.investigation import Claim, InvestigationStatus
from clear_context.repositories.investigation import InvestigationRepository
from clear_context.services.investigation_research import (
    InvestigationResearch,
    ResearchBudget,
)


def completion(value):
    return {
        "choices": [{"message": {"content": json.dumps(value)}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10},
    }


PLANNED_NEED = {
    "id": "n1",
    "description": "The bridge opened in 2017 and the mayor opened it",
    "status": "planned",
    "reason": None,
}
TWO_COMPONENTS = {
    "components": [
        {
            "description": "The bridge opened in 2017",
            "status": "contradicted",
            "explanation": "The record says 2019.",
            "evidence": [
                {
                    "evidence_id": "E1",
                    "relation": "contradicts",
                    "quote": "The bridge opened in 2019.",
                }
            ],
        },
        {
            "description": "The bridge was opened by the mayor",
            "status": "insufficient",
            "explanation": "The source does not say who opened it.",
            "evidence": [],
        },
    ]
}


PAGES = {
    "https://example.org/bridge": "The bridge opened in 2019.",
    "https://example.org/mayor": "The mayor opened the bridge in 2019.",
}


def run_research(
    monkeypatch,
    tmp_path,
    needs,
    judge_response,
    followup_response=None,
    budget=None,
    calls=None,
    progress=None,
):
    """Run the flow with fakes; judge_response may be a list consumed per judgment call."""
    from clear_context.services import investigation_research as module

    class Model:
        def __init__(self, settings):
            pass

        async def complete(self, payload, timeout):
            request = json.loads(payload["messages"][1]["content"])
            if payload["response_format"]["json_schema"]["name"] == "query_plan":
                claim_id = request["claims"][0]["id"]
                return completion(
                    {
                        "needs": [{**need, "claim_id": claim_id} for need in needs],
                        "questions": [
                            {
                                "need_ids": ["n1"],
                                "question": "When did it open?",
                                "queries": [
                                    {
                                        "text": "bridge opening year",
                                        "language": "en",
                                        "need_ids": ["n1"],
                                    }
                                ],
                            }
                        ],
                    }
                )
            name = payload["response_format"]["json_schema"]["name"]
            if calls is not None:
                calls.append(name)
            if name == "followup_queries":
                return completion(followup_response or {"queries": []})
            if isinstance(judge_response, list):
                response = judge_response.pop(0)
                return completion(response(request) if callable(response) else response)
            return completion(judge_response)

    class Selector(Model):
        async def select(self, payload, timeout):
            return completion(
                {
                    "selections": [
                        {
                            "need_id": "n1",
                            "status": "relevant",
                            "paragraph_ids": ["P001"],
                            "reason": "Opening date",
                        }
                    ]
                }
            )

    class Search:
        def __init__(self, timeout):
            pass

        def search(self, request):
            url = (
                "https://example.org/mayor"
                if "mayor" in request.query
                else ("https://example.org/bridge")
            )
            return {"query": request.query, "results": [{"title": "Record", "url": url}]}

        def extract_payload(self, url):
            return {"urls": [url]}

        def extract(self, url):
            return {"results": [{"url": url, "raw_content": PAGES[url]}]}

        def close(self):
            pass

    monkeypatch.setattr(module, "MetaStructuredProvider", Model)
    monkeypatch.setattr(module, "MetaPassageProvider", Selector)
    monkeypatch.setattr(module, "TavilyKeyless", Search)
    model = ModelSelection(alias="spark", api_model_id="muse-spark-1.3", training_use=False)
    claim = Claim(id=uuid4(), text="The bridge opened in 2017 and the mayor opened it.")
    research = InvestigationResearch(
        Settings(_env_file=None),
        {"research": model, "judge": model},
        tmp_path / "research.sqlite",
        budget,
    )
    return claim, research.run(uuid4(), [claim], progress)


def test_research_pipeline_binds_queries_sources_and_components(monkeypatch, tmp_path):
    claim, report = run_research(monkeypatch, tmp_path, [PLANNED_NEED], TWO_COMPONENTS)
    assert report.findings[0].assessment == "unresolved"
    assert report.findings[0].components[0].status == "contradicted"
    assert report.findings[0].components[0].evidence_relations
    # The passage reviewed for the need stays visible under the unsettled detail.
    assert report.findings[0].components[1].context_evidence_ids
    assert report.evidence[0].excerpt == "The bridge opened in 2019."
    assert report.sources[0].url == "https://example.org/bridge"

    engine = create_database(tmp_path / "application.sqlite")
    Base.metadata.create_all(engine)
    repository = InvestigationRepository(create_session_factory(engine))
    investigation = repository.create(claim.text, mode="meta")
    repository.transition(investigation.id, InvestigationStatus.RUNNING, "graph_started")
    report.investigation_id = UUID(investigation.id)
    repository.complete(report)
    saved = repository.get_report(investigation.id)
    assert saved.findings[0].components == report.findings[0].components
    assert saved.evidence[0].excerpt == report.evidence[0].excerpt
    engine.dispose()


def test_failed_assessment_is_not_reported_as_insufficient_evidence(monkeypatch, tmp_path):
    _, report = run_research(monkeypatch, tmp_path, [PLANNED_NEED], {"components": []})
    component = report.findings[0].components[0]
    assert component.status == "not_assessed"
    assert "did not complete" in component.explanation
    assert not component.evidence_ids and not component.context_evidence_ids
    assert any("did not complete" in item for item in report.limitations)


def test_deferred_need_is_reported_as_not_assessed(monkeypatch, tmp_path):
    deferred = {
        "id": "n2",
        "description": "Visitor numbers in the opening year",
        "status": "budget_deferred",
        "reason": "Lower priority than the opening date.",
    }
    _, report = run_research(monkeypatch, tmp_path, [PLANNED_NEED, deferred], TWO_COMPONENTS)
    components = report.findings[0].components
    assert [c.status for c in components] == ["contradicted", "insufficient", "not_assessed"]
    assert "search budget" in components[2].explanation


MAYOR_NEED = {
    "id": "n1",
    "description": "The mayor opened the bridge",
    "status": "planned",
    "reason": None,
}
MAYOR_INSUFFICIENT = {
    "components": [
        {
            "description": "The mayor opened the bridge",
            "status": "insufficient",
            "explanation": "The record gives the year but not who opened it.",
            "evidence": [],
        }
    ]
}


def cite_mayor(request):
    alias = next(e["id"] for e in request["evidence"] if "mayor" in e["text"])
    return {
        "components": [
            {
                "description": "The mayor opened the bridge",
                "status": "supported",
                "explanation": "The second source names the mayor.",
                "evidence": [
                    {
                        "evidence_id": alias,
                        "relation": "supports",
                        "quote": "The mayor opened the bridge in 2019.",
                    }
                ],
            }
        ]
    }


MAYOR_FOLLOWUP = {
    "queries": [
        {
            "need_id": "n1",
            "text": "mayor bridge opening ceremony",
            "language": "en",
            "reason": "Targets who opened the bridge.",
        }
    ]
}


def test_followup_search_reassesses_an_insufficient_need(monkeypatch, tmp_path):
    calls, steps = [], []
    _, report = run_research(
        monkeypatch,
        tmp_path,
        [MAYOR_NEED],
        [MAYOR_INSUFFICIENT, cite_mayor],
        MAYOR_FOLLOWUP,
        calls=calls,
        progress=steps.append,
    )
    component = report.findings[0].components[0]
    assert component.status == "supported"
    assert report.findings[0].assessment == "unresolved"
    cited = next(e for e in report.evidence if e.id == component.evidence_ids[0])
    assert cited.excerpt == "The mayor opened the bridge in 2019."
    # Reports list cited sources only; the first page no longer backs this detail.
    assert {s.url for s in report.sources} == {"https://example.org/mayor"}
    assert calls.count("followup_queries") == 1
    assert "followup_research" in steps
    assert "followup_planning" in {usage.task for usage in report.model_usage}
    assert any("1 gained new passages" in item for item in report.limitations)


def test_followup_without_new_passages_keeps_the_first_assessment(monkeypatch, tmp_path):
    repeated = {
        "queries": [
            {
                "need_id": "n1",
                "text": "Bridge  opening YEAR",
                "language": "en",
                "reason": "Same query again.",
            }
        ]
    }
    calls = []
    _, report = run_research(
        monkeypatch, tmp_path, [MAYOR_NEED], [MAYOR_INSUFFICIENT], repeated, calls=calls
    )
    assert report.findings[0].components[0].status == "insufficient"
    # The repeated query is dropped, so no second judgment call is made.
    assert calls.count("followup_queries") == 1
    assert len([c for c in calls if c not in {"query_plan", "followup_queries"}]) == 1


def test_followup_round_can_be_disabled_by_budget(monkeypatch, tmp_path):
    calls = []
    _, report = run_research(
        monkeypatch,
        tmp_path,
        [MAYOR_NEED],
        [MAYOR_INSUFFICIENT],
        MAYOR_FOLLOWUP,
        budget=ResearchBudget(followup_queries=0),
        calls=calls,
    )
    assert "followup_queries" not in calls
    assert report.findings[0].components[0].status == "insufficient"
