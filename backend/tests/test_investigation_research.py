import json
from uuid import UUID, uuid4

from clear_context.core.settings import ModelSelection, Settings
from clear_context.db.base import Base
from clear_context.db.session import create_database, create_session_factory
from clear_context.domain.investigation import Claim, InvestigationStatus
from clear_context.repositories.investigation import InvestigationRepository
from clear_context.services.investigation_research import InvestigationResearch


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


def run_research(monkeypatch, tmp_path, needs, judge_response):
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
            return {
                "query": request.query,
                "results": [{"title": "Record", "url": "https://example.org/bridge"}],
            }

        def extract_payload(self, url):
            return {"urls": [url]}

        def extract(self, url):
            return {"results": [{"url": url, "raw_content": "The bridge opened in 2019."}]}

        def close(self):
            pass

    monkeypatch.setattr(module, "MetaStructuredProvider", Model)
    monkeypatch.setattr(module, "MetaPassageProvider", Selector)
    monkeypatch.setattr(module, "TavilyKeyless", Search)
    model = ModelSelection(alias="spark", api_model_id="muse-spark-1.3", training_use=False)
    claim = Claim(id=uuid4(), text="The bridge opened in 2017 and the mayor opened it.")
    research = InvestigationResearch(
        Settings(_env_file=None), {"research": model, "judge": model}, tmp_path / "research.sqlite"
    )
    return claim, research.run(uuid4(), [claim])


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
