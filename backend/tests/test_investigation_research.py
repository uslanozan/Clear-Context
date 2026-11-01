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
                        "needs": [
                            {"about_attached_media": False, **need, "claim_id": claim_id}
                            for need in needs
                        ],
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


def test_text_only_research_uses_the_selected_planner_without_image_context(monkeypatch, tmp_path):
    requests = []
    run_research(
        monkeypatch,
        tmp_path,
        [PLANNED_NEED],
        TWO_COMPONENTS,
        budget=ResearchBudget(followup_queries=0),
        planner_requests=requests,
    )
    system = requests[0]["messages"][0]["content"]
    # v7 = v5 rules, then v6 image rules, then not_checkable and main-claim priority.
    assert system.index("Plan web research") < system.index("image_context")
    assert system.index("image_context") < system.index("not_checkable")
    assert "image_context" not in json.loads(requests[0]["messages"][1]["content"])


def test_not_checkable_need_is_reported_without_research(monkeypatch, tmp_path):
    opinion = {
        "id": "n2",
        "description": "Rakiplerin bu duyguyu bilmediği",
        "status": "not_checkable",
        "reason": "Bir grubun ne hissettiğine dair değer yargısı.",
    }
    calls = []
    _, report = run_research(
        monkeypatch,
        tmp_path,
        [PLANNED_NEED, opinion],
        TWO_COMPONENTS,
        budget=ResearchBudget(followup_queries=0),
        calls=calls,
        claim_text="Köprü 2017'de açıldı; rakipler bu duyguyu bilmez.",
    )
    component = report.findings[0].components[-1]
    assert component.status == "not_assessed"
    assert component.explanation.startswith("Araştırılmadı: görüş, değer yargısı")
    assert not component.evidence_ids
    # Only the planned need was judged.
    assert calls.count("component_assessment") == 1


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


def test_one_unusable_search_answer_skips_only_that_query():
    from clear_context.schemas.retrieval import ResearchQuery, SearchRequest

    class Session:
        halted = False

        def __init__(self):
            self.searched, self.read = [], []

        def search(self, case_id, query_id):
            self.searched.append(query_id)
            if query_id == "q1":
                raise RetrievalFailure("invalid_response")
            return {"results": [{"url": "https://example.org/primary", "score": 0.9}]}

        def read_source(self, source):
            self.read.append(source)
            return "page-1"

    queries = [
        ResearchQuery(id=q, request=SearchRequest(query=q, language="en"), need_ids=["n1"])
        for q in ("q1", "q2")
    ]
    session, limitations = Session(), []
    complete = InvestigationResearch._search(
        session, None, "case", queries, {}, {}, {}, 10, limitations
    )
    assert complete and session.searched == ["q1", "q2"] and len(session.read) == 1
    assert limitations == ["One search returned an unusable answer and was skipped."]


def test_failed_planning_keeps_the_claims_and_says_research_did_not_run(monkeypatch, tmp_path):
    from clear_context.providers.meta_structured import ModelResponseFailure
    from clear_context.services import investigation_research as module

    class Failing:
        def __init__(self, settings):
            pass

        async def complete(self, payload, timeout):
            raise ModelResponseFailure("rate_limited", 429)

    monkeypatch.setattr(module, "MetaStructuredProvider", Failing)
    model = ModelSelection(alias="spark", api_model_id="muse-spark-1.3", training_use=False)
    claim = Claim(id=uuid4(), text="The bridge opened in 2017 and the mayor opened it.")
    research = InvestigationResearch(
        Settings(_env_file=None), {"research": model, "judge": model}, tmp_path / "r.sqlite"
    )
    report = research.run(uuid4(), [claim])
    assert report.claims == [claim]
    assert report.findings[0].assessment == "unresolved"
    assert "rate_limited" in report.findings[0].explanation
    assert report.limitations == [
        "Research planning did not complete (rate_limited); claims were not researched."
    ]


def test_an_invalid_plan_is_requested_once_more(monkeypatch, tmp_path):
    from clear_context.services import investigation_research as module

    answers = []

    class Planner:
        def __init__(self, settings):
            pass

        async def complete(self, payload, timeout):
            answers.append(payload["response_format"]["json_schema"]["name"])
            # Every plan breaks the schema: research is not run after the second try.
            return completion({"needs": "not a list"})

    monkeypatch.setattr(module, "MetaStructuredProvider", Planner)
    model = ModelSelection(alias="spark", api_model_id="muse-spark-1.3", training_use=False)
    claim = Claim(id=uuid4(), text="The bridge opened in 2017.")
    research = InvestigationResearch(
        Settings(_env_file=None), {"research": model, "judge": model}, tmp_path / "r.sqlite"
    )
    report = research.run(uuid4(), [claim])
    assert [name for name in answers if name == "query_plan"] == ["query_plan"] * 2
    assert "invalid_plan" in report.findings[0].explanation
    assert [u.task for u in report.model_usage].count("query_planning") == 2


def test_a_second_valid_plan_lets_research_continue(monkeypatch, tmp_path):
    from clear_context.services import investigation_research as module

    original = module.parse_planner_response
    attempts = []

    def flaky(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise ValueError("Plan references an unknown claim.")
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "parse_planner_response", flaky)
    claim, report = run_research(monkeypatch, tmp_path, [PLANNED_NEED], TWO_COMPONENTS)
    assert len(attempts) == 2
    # The second plan was used: research ran and assessed the planned need.
    assert report.findings[0].components[0].status in {"supported", "contradicted"}
    assert not any("did not complete" in item for item in report.limitations)


def test_the_users_description_of_media_is_never_grouped(monkeypatch, tmp_path):
    from clear_context.services import investigation_research as module
    from clear_context.services.claim_groups import Grouping
    from clear_context.services.language import LanguageDecision

    seen = []

    async def record_groups(claims, *args):
        seen.extend(text for _, text in claims)
        return Grouping({})

    async def language(*args, **kwargs):
        return LanguageDecision("en", 1.0, "langdetect")

    async def research(self, investigation_id, claims, *args, **kwargs):
        return module.research_not_run(investigation_id, claims, "test")

    monkeypatch.setattr(module, "group_claims", record_groups)
    monkeypatch.setattr(module, "detect_language", language)
    monkeypatch.setattr(InvestigationResearch, "_research", research)
    caption = "The governor warned of dramatic flooding"
    claims = [
        Claim(id=uuid4(), text=caption),
        Claim(id=uuid4(), text="our primary concern remains dramatic flooding"),
        Claim(id=uuid4(), text="20 inches of rain fell"),
    ]
    settings = Settings(
        _env_file=None, app_mode="meta", allow_paid_api_calls=True, meta_api_key="k"
    )
    model = ModelSelection(alias="spark", api_model_id="muse-spark-1.3", training_use=False)
    service = InvestigationResearch(settings, {"research": model, "judge": model}, tmp_path / "r")
    service.run(uuid4(), claims, user_text=f"{caption}.")
    assert caption not in seen and len(seen) == 2


def test_a_need_about_the_attached_media_is_not_searched_on_the_web(monkeypatch, tmp_path):
    # Searching the web for "a blue screen video" finds other videos, never the attached one.
    calls = []
    _, report = run_research(
        monkeypatch,
        tmp_path,
        [{**PLANNED_NEED, "about_attached_media": True}],
        [MAYOR_INSUFFICIENT],
        MAYOR_FOLLOWUP,
        calls=calls,
    )
    component = report.findings[0].components[0]
    assert component.status == "insufficient"
    assert report.sources == []
    # No follow-up round either: another web search cannot settle it.
    assert calls.count("followup_queries") == 0
    assert any("same picture or video" in item for item in report.limitations)


def test_other_needs_are_still_searched_beside_a_media_need(monkeypatch, tmp_path):
    _, report = run_research(
        monkeypatch,
        tmp_path,
        [{**PLANNED_NEED, "about_attached_media": False}],
        TWO_COMPONENTS,
    )
    assert report.findings[0].components[0].status == "contradicted"
    assert {s.url for s in report.sources} == {"https://example.org/bridge"}
    assert not any("same picture or video" in item for item in report.limitations)
