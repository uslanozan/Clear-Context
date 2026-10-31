import json
from uuid import UUID, uuid4

from clear_context.core.settings import ModelSelection, Settings
from clear_context.db.base import Base
from clear_context.db.session import create_database, create_session_factory
from clear_context.domain.investigation import Claim, InvestigationStatus
from clear_context.providers.tavily import RetrievalFailure
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
    "https://example.org/blocked": None,
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
    mode=None,
    judge_profile="need_components_v2",
    claim_text="The bridge opened in 2017 and the mayor opened it.",
    first_url=None,
    media=None,
    planner_requests=None,
    **run_options,
):
    """Run the flow with fakes; judge_response may be a list consumed per judgment call."""
    from clear_context.services import investigation_research as module

    class Model:
        def __init__(self, settings):
            pass

        async def complete(self, payload, timeout):
            request = json.loads(payload["messages"][1]["content"])
            if payload["response_format"]["json_schema"]["name"] == "query_plan":
                if planner_requests is not None:
                    planner_requests.append(payload)
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
        def __init__(self, timeout, api_key=""):
            pass

        def search(self, request):
            url = (
                "https://example.org/mayor"
                if "mayor" in request.query
                else ("https://example.org/bridge")
            )
            urls = [first_url, url] if first_url else [url]
            return {
                "query": request.query,
                "results": [{"title": "Record", "url": u} for u in urls],
            }

        def extract_payload(self, url):
            return {"urls": [url]}

        def extract(self, url):
            if PAGES[url] is None:
                raise RetrievalFailure("extract_failed")
            return {"results": [{"url": url, "raw_content": PAGES[url]}]}

        def close(self):
            pass

    monkeypatch.setattr(module, "MetaStructuredProvider", Model)
    monkeypatch.setattr(module, "MetaPassageProvider", Selector)
    monkeypatch.setattr(module, "TavilyClient", Search)
    model = ModelSelection(alias="spark", api_model_id="muse-spark-1.3", training_use=False)
    claim = Claim(id=uuid4(), text=claim_text)
    research = InvestigationResearch(
        Settings(_env_file=None, research_judge_profile=judge_profile),
        {"research": model, "judge": model},
        tmp_path / "research.sqlite",
        budget,
    )
    return claim, research.run(uuid4(), [claim], progress, mode, media=media, **run_options)


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


def test_research_modes_change_budgets_not_methods(monkeypatch, tmp_path):
    from clear_context.services.investigation_research import RESEARCH_MODES

    fast, balanced, deep = (RESEARCH_MODES[m] for m in ("fast", "balanced", "deep"))
    assert balanced == ResearchBudget()
    assert fast.max_queries < balanced.max_queries < deep.max_queries
    assert fast.followup_queries == 0 < balanced.followup_queries < deep.followup_queries

    calls = []
    _, report = run_research(
        monkeypatch,
        tmp_path,
        [MAYOR_NEED],
        [MAYOR_INSUFFICIENT],
        MAYOR_FOLLOWUP,
        calls=calls,
        mode="fast",
    )
    assert "followup_queries" not in calls
    assert report.findings[0].components[0].status == "insufficient"


def test_two_investigations_citing_the_same_cached_page_both_persist(monkeypatch, tmp_path):
    engine = create_database(tmp_path / "application.sqlite")
    Base.metadata.create_all(engine)
    repository = InvestigationRepository(create_session_factory(engine))
    for _ in range(2):
        claim, report = run_research(monkeypatch, tmp_path, [PLANNED_NEED], TWO_COMPONENTS)
        investigation = repository.create(claim.text, mode="meta")
        repository.transition(investigation.id, InvestigationStatus.RUNNING, "graph_started")
        report.investigation_id = UUID(investigation.id)
        repository.complete(report)
        assert (
            repository.get_report(investigation.id).sources[0].url == "https://example.org/bridge"
        )
    engine.dispose()


def test_anchored_judge_profile_assesses_the_claim_as_stated(monkeypatch, tmp_path):
    neutral = {**PLANNED_NEED, "description": "Whether the bridge opened in 2017"}
    seen = []

    def judge(request):
        seen.append(request)
        return {
            "components": [
                {
                    "description": "The bridge opened in 2017",
                    "status": "contradicted",
                    "explanation": "The record says 2019.",
                    "claim_quote": "The bridge opened in 2017",
                    "evidence": [
                        {
                            "evidence_id": "E1",
                            "relation": "contradicts",
                            "quote": "The bridge opened in 2019.",
                        }
                    ],
                }
            ]
        }

    _, report = run_research(
        monkeypatch,
        tmp_path,
        [neutral],
        [judge],
        budget=ResearchBudget(followup_queries=0),
        judge_profile="need_components_v3",
    )
    assert seen[0]["claim"] == "The bridge opened in 2017 and the mayor opened it."
    assert seen[0]["focus"] == "Whether the bridge opened in 2017"
    assert report.findings[0].components[0].status == "contradicted"


def test_unreadable_source_does_not_use_the_read_budget(monkeypatch, tmp_path):
    _, report = run_research(
        monkeypatch,
        tmp_path,
        [PLANNED_NEED],
        TWO_COMPONENTS,
        budget=ResearchBudget(max_source_reads=1, followup_queries=0),
        first_url="https://example.org/blocked",
    )
    assert any("extract_failed" in item for item in report.limitations)
    assert report.sources[0].url == "https://example.org/bridge"
    assert report.findings[0].components[0].status == "contradicted"


def test_system_explanations_follow_a_turkish_claim(monkeypatch, tmp_path):
    deferred = {
        "id": "n2",
        "description": "Açılış yılındaki ziyaretçi sayısı",
        "status": "budget_deferred",
        "reason": "Öncelik açılış yılında.",
    }
    _, report = run_research(
        monkeypatch,
        tmp_path,
        [PLANNED_NEED, deferred],
        TWO_COMPONENTS,
        budget=ResearchBudget(followup_queries=0),
        claim_text="Köprü 2017'de açıldı ve açılışı belediye başkanı yaptı.",
    )
    finding = report.findings[0]
    assert finding.explanation.startswith("İddianın tamamı için kapsam doğrulanmadı")
    assert finding.components[-1].explanation == (
        "Bu araştırmanın arama bütçesi içinde araştırılmadı."
    )


def test_pages_matching_the_image_are_read_beside_text_search(monkeypatch, tmp_path):
    from sqlalchemy import create_engine, text

    from clear_context.domain.investigation import (
        ImageMatch,
        MediaAnalysis,
        MediaFinding,
        MediaOrigin,
    )

    finding = MediaFinding(
        id=uuid4(),
        kind="image",
        mime_type="image/jpeg",
        filename="post.jpg",
        analysis=MediaAnalysis(
            status="analyzed",
            content_type="photo",
            observations=["A bridge over a river."],
            context_cues=["Signs are in Hungarian."],
        ),
        origin=MediaOrigin(
            status="matches_found",
            provider="serpapi_lens",
            matches=[
                ImageMatch(
                    page_url="https://www.instagram.com/p/1/",
                    page_title="Reposted bridge photo",
                    match="full",
                ),
                ImageMatch(
                    page_url="https://example.org/mayor",
                    page_title="Bridge opening, 2019",
                    match="full",
                    date_text="Feb 12, 2019",
                    published_on="2019-02-12",
                ),
            ],
        ),
    )
    requests = []
    _, report = run_research(
        monkeypatch,
        tmp_path,
        [PLANNED_NEED],
        TWO_COMPONENTS,
        budget=ResearchBudget(max_source_reads=1, followup_queries=0),
        media=[finding],
        planner_requests=requests,
    )
    context = json.loads(requests[0]["messages"][1]["content"])
    assert context["image_context"][0]["matching_page_titles"] == [
        "Reposted bridge photo",
        "Bridge opening, 2019",
    ]
    # The image-aware planner extends the selected planner's rules.
    system = requests[0]["messages"][0]["content"]
    assert "image_context" in system and "Plan web research" in system
    # The matching page is read in addition to the one text-search source; the social
    # feed is skipped.
    engine = create_engine("sqlite:///" + (tmp_path / "research.sqlite").as_posix())
    with engine.connect() as conn:
        read = conn.execute(
            text("SELECT s.url FROM research_pages p JOIN research_sources s ON s.id = p.source_id")
        )
        urls = {row[0] for row in read}
        hits = conn.execute(
            text("SELECT result FROM research_hits WHERE query_id = 'image_matches'")
        ).all()
    engine.dispose()
    assert urls == {"https://example.org/mayor", "https://example.org/bridge"}
    assert len(hits) == 1
    assert json.loads(hits[0][0])["published_date"] == "2019-02-12"
    assert not any("could not be read" in item for item in report.limitations)


def test_text_only_research_keeps_the_selected_planner(monkeypatch, tmp_path):
    requests = []
    run_research(
        monkeypatch,
        tmp_path,
        [PLANNED_NEED],
        TWO_COMPONENTS,
        budget=ResearchBudget(followup_queries=0),
        planner_requests=requests,
    )
    assert "image_context" not in requests[0]["messages"][0]["content"]
    assert "image_context" not in json.loads(requests[0]["messages"][1]["content"])


def test_low_scored_search_results_are_not_read():
    from clear_context.schemas.retrieval import ResearchQuery, SearchRequest

    class Session:
        def __init__(self):
            self.read = []

        def search(self, case_id, query_id):
            return {
                "results": [
                    {"url": "https://example.org/unrelated", "score": 0.04},
                    {"url": "https://example.org/primary", "score": 0.45},
                    {"url": "https://example.org/unscored"},
                ]
            }

        def read_source(self, source):
            self.read.append(source)
            return f"page-{len(self.read)}"

    session, limitations = Session(), []
    query = ResearchQuery(
        id="q1", request=SearchRequest(query="bridge", language="en"), need_ids=["n1"]
    )
    complete = InvestigationResearch._search(
        session, None, "case", [query], {}, {}, {}, 10, limitations, min_score=0.30
    )
    # The unrelated result is skipped; a primary source at 0.45 and an unscored result are read.
    assert complete and len(session.read) == 2
    assert limitations == ["1 search result(s) scored below 0.30 for relevance were not read."]
