"""Bounded text research using saved query, source and judgment receipts."""

import asyncio
import time
from dataclasses import dataclass
from itertools import zip_longest
from uuid import NAMESPACE_URL, UUID, uuid5

from clear_context.core.judges import load_judge
from clear_context.core.passage_selectors import load_selector
from clear_context.core.query_catalog import build_planner_request, parse_planner_response
from clear_context.core.settings import PROJECT_ROOT
from clear_context.domain.investigation import (
    Assessment,
    Evidence,
    Finding,
    FindingComponent,
    InvestigationReport,
    ModelUsage,
    ResearchSummary,
    Source,
)
from clear_context.providers.meta_passages import MetaPassageProvider
from clear_context.providers.meta_structured import MetaStructuredProvider, ModelResponseFailure
from clear_context.providers.reverse_image import looks_like_fact_check, readable_matches
from clear_context.providers.tavily import RetrievalFailure, TavilyClient
from clear_context.repositories.judgment import JudgmentRepository
from clear_context.repositories.retrieval import RetrievalRepository, identity
from clear_context.schemas.retrieval import (
    ResearchQuery,
    SavedResearchPlan,
    SearchRequest,
    canonical_source_url,
)
from clear_context.services.evidence_judgment import EvidenceJudgmentService, JudgmentJob
from clear_context.services.followup_queries import (
    ResearchGap,
    build_followup_request,
    classify_gap,
    parse_followup_response,
)
from clear_context.services.language import detect_language
from clear_context.services.passage_selection import PassageSelectionService, SelectionJob
from clear_context.services.query_planning import PlanningClaim
from clear_context.services.report_text import report_language, report_text
from clear_context.services.retrieval import RetrievalSession, load_retrieval_policy


@dataclass(frozen=True)
class Subject:
    """The pages being checked: their source IDs and reported publication date."""

    sources: frozenset[str] = frozenset()
    published_on: object = None


@dataclass(frozen=True)
class ResearchBudget:
    """Per-investigation call limits; research modes vary these, not the methods."""

    max_queries: int = 6
    # Every readable page that search found is read and searched for passages; reading
    # only the first few lost evidence in measured runs (experiment read-all-v1). These
    # caps only bound time. Modes differ by how much they search.
    max_source_reads: int = 20
    max_selection_calls: int = 20
    max_judgment_calls: int = 6
    # One follow-up round for needs left insufficient; 0 disables it.
    followup_queries: int = 2
    followup_source_reads: int = 10
    followup_selection_calls: int = 10
    followup_judgment_calls: int = 2
    # Pages where reverse image search found the attached image; read in addition to
    # text-search sources.
    image_match_reads: int = 2


RESEARCH_MODES = {
    "fast": ResearchBudget(
        max_queries=3,
        max_source_reads=12,
        max_selection_calls=12,
        max_judgment_calls=4,
        followup_queries=0,
        followup_source_reads=0,
        followup_selection_calls=0,
        followup_judgment_calls=0,
        image_match_reads=1,
    ),
    "balanced": ResearchBudget(),
    "deep": ResearchBudget(
        max_queries=10,
        max_source_reads=30,
        max_selection_calls=30,
        max_judgment_calls=10,
        followup_queries=4,
        followup_source_reads=15,
        followup_selection_calls=15,
        followup_judgment_calls=4,
        image_match_reads=3,
    ),
}


def summarize(plan, judgments) -> ResearchSummary:
    """Count how each research need ended; budget-limited claims can be continued later."""
    outcome = {row["need_ids"][0]: row["status"] for row in judgments}
    limited = [
        need
        for need in plan.needs
        if need.status == "budget_deferred" or outcome.get(need.id) == "call_budget_exhausted"
    ]
    planned = [need for need in plan.needs if need.status == "planned"]
    return ResearchSummary(
        planned=len(planned),
        assessed=sum(1 for need in planned if outcome.get(need.id) == "assessed"),
        budget_limited=len(limited),
        needs_context=sum(1 for need in plan.needs if need.status == "needs_context"),
        not_checkable=sum(1 for need in plan.needs if need.status == "not_checkable"),
        failed=sum(
            1
            for need in planned
            if outcome.get(need.id) not in {None, "assessed", "call_budget_exhausted"}
        ),
        budget_limited_claim_ids=list(dict.fromkeys(UUID(need.claim_id) for need in limited)),
    )


def image_context(media) -> list[dict]:
    """Planner context from analyzed images; untrusted descriptions, not claims or evidence."""
    context = []
    for index, finding in enumerate(media or [], 1):
        analysis = finding.analysis
        if analysis.status != "analyzed":
            continue
        context.append(
            {
                "image": index,
                "content_type": analysis.content_type,
                "observations": analysis.observations,
                "context_cues": analysis.context_cues,
                "matching_page_titles": [
                    match.page_title for match in finding.origin.matches[:8] if match.page_title
                ],
                "fact_check_titles": [
                    review.title for review in finding.prior_checks.reviews[:5] if review.title
                ],
            }
        )
    return context


def stable_uuid(kind, value):
    return uuid5(NAMESPACE_URL, f"clear-context:{kind}:{value}")


def usage_record(task, model, usage):
    usage = usage or {}
    return ModelUsage(
        task=task,
        model_id=model,
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
        cached_input_tokens=(usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
    )


class InvestigationResearch:
    def __init__(self, settings, models, workspace, budget: ResearchBudget | None = None):
        self.settings, self.models, self.workspace = settings, models, workspace
        self.budget = budget or ResearchBudget()

    def run(
        self,
        investigation_id,
        claims,
        progress=None,
        mode=None,
        media=None,
        subject_urls=(),
        published_on=None,
    ):
        """Research claims. subject_urls are the pages being checked, never read as evidence;
        published_on is when the checked page was published, if a search index reported it."""
        budget = RESEARCH_MODES[mode] if mode else self.budget
        subject = Subject(
            sources=frozenset(identity("s_", canonical_source_url(url)) for url in subject_urls),
            published_on=published_on,
        )
        return asyncio.run(
            self._run(investigation_id, claims, progress, budget, media or [], subject)
        )

    async def _run(self, investigation_id, claims, progress, budget, media, subject=None):
        subject = subject or Subject()
        # Decide system text language once from all claims; one short claim misleads detection.
        text = "\n".join(dict.fromkeys(c.text for c in claims))
        language = await detect_language(
            text,
            MetaStructuredProvider(self.settings),
            self.models["research"].api_model_id,
            PROJECT_ROOT / "config/prompts.yaml",
        )
        with report_language(language.code):
            report = await self._research(
                investigation_id, claims, progress, budget, media, subject
            )
        if language.usage:
            report.model_usage.insert(0, language.usage)
        return report

    async def _research(self, investigation_id, claims, progress, budget, media, subject):
        meta = MetaStructuredProvider(self.settings)
        planning_claims = [
            PlanningClaim(
                id=str(c.id), statement=c.statement or c.text, quote=c.text, group=c.group
            )
            for c in claims
        ]
        if not planning_claims:
            return InvestigationReport(
                investigation_id=investigation_id,
                mode="meta",
                claims=[],
                sources=[],
                evidence=[],
                findings=[],
                limitations=["No claims were available for research."],
            )
        images = image_context(media)
        request, profile = build_planner_request(
            planning_claims,
            planners_path=PROJECT_ROOT / "config/query_planners.yaml",
            prompts_path=PROJECT_ROOT / "config/prompts.yaml",
            source_language="auto",
            source_published_at=subject.published_on.isoformat() if subject.published_on else None,
            maximum_queries=budget.max_queries,
            model=self.models["research"].api_model_id,
            # The selected planner (v7) handles text and image context alike.
            image_context=images or None,
        )
        body = await meta.complete(request, self.settings.meta_timeout_seconds)
        usage = [
            usage_record("query_planning", self.models["research"].api_model_id, body.get("usage"))
        ]
        plan = parse_planner_response(
            body["choices"][0]["message"]["content"],
            planning_claims,
            budget.max_queries,
            profile,
        )
        if progress:
            progress("plan_queries")
        needs = [
            {k: item[k] for k in ("id", "claim_id", "description", "status")}
            for item in plan["needs"]
        ]
        queries = []
        for question in plan["questions"]:
            for q in question["queries"]:
                queries.append(
                    {
                        "id": f"q{len(queries) + 1}",
                        "request": {
                            "query": q["text"],
                            "language": q["language"],
                            "max_results": 3,
                        },
                        "need_ids": q["need_ids"],
                    }
                )
        saved = SavedResearchPlan.model_validate(
            {
                "case_id": str(investigation_id),
                "claims": [
                    {"id": c.id, "statement": c.statement, "quote": c.quote}
                    for c in planning_claims
                ],
                "needs": needs,
                "queries": queries,
            }
        )
        research = RetrievalRepository(self.workspace)
        tavily = TavilyClient(timeout=30, api_key=self.settings.tavily_api_key.get_secret_value())
        limitations = ["Evidence assessments do not establish source reliability."]
        try:
            research.register_plan(saved)
            policy = load_retrieval_policy(PROJECT_ROOT / "config/retrieval.yaml")
            policy = policy.model_copy(
                update={
                    "max_search_calls": budget.max_queries + budget.followup_queries,
                    # Extra extract calls let a readable source replace an unreadable one.
                    "max_extract_calls": 2
                    * (
                        budget.max_source_reads
                        + budget.followup_source_reads
                        + budget.image_match_reads
                    ),
                    "max_followup_queries": budget.followup_queries,
                }
            )
            session = RetrievalSession(research, tavily, policy)
            page_needs, hits = {}, {}
            # The checked page is marked unreadable so it never becomes its own evidence.
            read_sources = dict.fromkeys(subject.sources)
            match_reads = self._read_image_matches(
                session,
                research,
                saved,
                media,
                budget.image_match_reads,
                read_sources,
                page_needs,
                limitations,
            )
            search_complete = self._search(
                session,
                research,
                saved.case_id,
                saved.queries,
                read_sources,
                page_needs,
                hits,
                budget.max_source_reads + match_reads,
                limitations,
                min_score=self.settings.search_min_score,
            )
            if progress and search_complete:
                progress("retrieve_sources")
            selections = await self._select(
                research, saved.case_id, page_needs, budget.max_selection_calls
            )
            if progress and not any(
                s["status"] not in {"selected", "not_found"} for s in selections
            ):
                progress("select_passages")
            usage.extend(
                usage_record("passage_selection", self.models["research"].api_model_id, s["usage"])
                for s in selections
                if s.get("usage") and not s.get("cached")
            )
            receipts = [s["selection_id"] for s in selections if s.get("selection_id")]
            if any(s["status"] not in {"selected", "not_found"} for s in selections):
                limitations.append("Some sources could not be evaluated for relevant passages.")
            active = [n for n in saved.needs if n.status == "planned"]
            judgments = await self._judge(
                meta,
                research,
                saved.case_id,
                [n.id for n in active],
                receipts,
                budget.max_judgment_calls,
            )
            if progress and all(j["status"] == "assessed" for j in judgments):
                progress("assess_components")
            usage.extend(
                usage_record("evidence_judgment", self.models["judge"].api_model_id, j["usage"])
                for j in judgments
                if j.get("usage") and not j.get("cached")
            )
            if budget.followup_queries and search_complete and not session.halted:
                judgments, receipts = await self._follow_up(
                    meta,
                    session,
                    research,
                    saved,
                    judgments,
                    receipts,
                    page_needs,
                    hits,
                    read_sources,
                    limitations,
                    usage,
                    progress,
                    budget,
                    match_reads,
                )
            report = self._report(
                investigation_id, claims, saved, judgments, research, limitations, receipts
            )
            report.model_usage = usage
            return report
        finally:
            tavily.close()
            research.close()

    @staticmethod
    def _read_image_matches(
        session, research, saved, media, limit, read_sources, page_needs, limitations
    ):
        """Read published fact checks of the attached image and pages where it appears.

        Fact checks and other pages alternate, so an early copy of the image is read even
        when several fact checks exist. Pages are read for every planned need; returns the
        number of pages read.
        """
        planned = [need.id for need in saved.needs if need.status == "planned"]
        if not planned or limit <= 0:
            return 0
        # The review date and the provider's displayed date become the page date.
        checks, pages = [], []
        for finding in media:
            checks.extend(
                {
                    "title": review.title or review.url,
                    "url": review.url,
                    "content": None,
                    "published_date": review.review_date.isoformat()
                    if review.review_date
                    else None,
                }
                for review in finding.prior_checks.reviews[:limit]
            )
            if finding.origin.status == "matches_found":
                matches = readable_matches(finding.origin, 3 * limit)
                ordered = [m for m in matches if not looks_like_fact_check(m)]
                ordered += [m for m in matches if looks_like_fact_check(m)]
                pages.extend(
                    {
                        "title": match.page_title or match.page_url,
                        "url": match.page_url,
                        "content": None,
                        "published_date": match.published_on.isoformat()
                        if match.published_on
                        else None,
                    }
                    for match in ordered[:limit]
                )
        results = [item for pair in zip_longest(checks, pages) for item in pair if item is not None]
        unique = {}
        for result in results:
            try:
                unique.setdefault(canonical_source_url(result["url"]), result)
            except ValueError:
                continue
        results = list(unique.values())
        if not results:
            return 0
        try:
            research.add_image_matches(
                saved.case_id, "image_matches", planned, results, time.time()
            )
        except ValueError:
            limitations.append("Reverse image matches could not be recorded for research.")
            return 0
        reads = 0
        for result in results:
            if reads >= limit:
                break
            try:
                source = identity("s_", canonical_source_url(result["url"]))
                if source in read_sources:
                    continue
                read_sources[source] = None
                read_sources[source] = session.read_source(source)
                page_needs[read_sources[source]] = set(planned)
                reads += 1
            except (RetrievalFailure, ValueError, KeyError) as error:
                code = getattr(error, "code", "invalid_source")
                limitations.append(f"A page matching the image could not be read ({code}).")
                if session.halted:
                    break
        return reads

    @staticmethod
    def _search(
        session,
        research,
        case_id,
        queries,
        read_sources,
        page_needs,
        hits,
        source_limit,
        limitations,
        min_score=0.0,
    ):
        """Run queries and read new sources up to source_limit; False if search stopped.

        Results scored below min_score by the search provider are not read: in measured runs
        they were unrelated pages, while useful primary sources scored well above it.
        """
        skipped = set()
        for query in queries:
            try:
                response = session.search(case_id, query.id)
            except RetrievalFailure as error:
                limitations.append(f"Search stopped: {error.code}.")
                return False
            results = response.get("results", [])
            for need_id in query.need_ids:
                hits[need_id] = hits.get(need_id, 0) + len(results)
            for hit in results:
                score = hit.get("score")
                if isinstance(score, int | float) and score < min_score:
                    skipped.add(hit.get("url"))
                    continue
                try:
                    source = identity("s_", canonical_source_url(hit["url"]))
                    if source not in read_sources:
                        if sum(1 for page in read_sources.values() if page) >= source_limit:
                            if "Source read budget reached." not in limitations:
                                limitations.append("Source read budget reached.")
                            continue
                        # Mark before reading so an unreadable source is not retried; only
                        # pages that were read count toward the source budget.
                        read_sources[source] = None
                        read_sources[source] = session.read_source(source)
                        page_needs[read_sources[source]] = set()
                    page = read_sources[source]
                    if page:
                        page_needs[page].update(query.need_ids)
                except (RetrievalFailure, ValueError, KeyError) as error:
                    code = getattr(error, "code", "invalid_source")
                    limitations.append(f"A source could not be read ({code}).")
        if skipped:
            limitations.append(
                f"{len(skipped)} search result(s) scored below {min_score:.2f} "
                "for relevance were not read."
            )
        return True

    async def _select(self, research, case_id, page_needs, max_calls):
        method, selector, selector_limits, system = load_selector(
            PROJECT_ROOT / "config/passage_selectors.yaml", PROJECT_ROOT / "config/prompts.yaml"
        )
        service = PassageSelectionService(
            research,
            MetaPassageProvider(self.settings),
            method,
            selector,
            selector_limits.model_copy(update={"max_model_calls": max_calls}),
            system,
            self.models["research"],
        )
        return await service.select_pages(
            [
                SelectionJob(case_id, page, tuple(sorted(ids)))
                for page, ids in page_needs.items()
                if ids
            ]
        )

    async def _judge(self, meta, research, case_id, need_ids, receipts, max_calls):
        judge_method, limits, judge_prompt, contract = load_judge(
            PROJECT_ROOT / "config/judges.yaml",
            PROJECT_ROOT / "config/prompts.yaml",
            method=self.settings.research_judge_profile,
        )
        judge = EvidenceJudgmentService(
            JudgmentRepository(research),
            meta,
            judge_method,
            limits.model_copy(update={"max_model_calls": max_calls}),
            judge_prompt,
            self.models["judge"],
            response_contract=contract,
        )
        return await judge.assess(
            [JudgmentJob(case_id, (need_id,), tuple(receipts)) for need_id in need_ids]
        )

    async def _follow_up(
        self,
        meta,
        session,
        research,
        saved,
        judgments,
        receipts,
        page_needs,
        hits,
        read_sources,
        limitations,
        usage,
        progress,
        budget,
        match_reads=0,
    ):
        """Search once more for needs the assessment left insufficient, within the budget."""
        packets = JudgmentRepository(research)
        statements = {claim.id: claim.statement for claim in saved.claims}
        needs = {need.id: need for need in saved.needs}
        previous = {}
        for query in saved.queries:
            for need_id in query.need_ids:
                previous.setdefault(need_id, []).append(query.request.query)
        gaps, passages_before = [], {}
        for row in judgments:
            if row["status"] != "assessed":
                continue
            missing = [
                c["explanation"]
                for c in row["result"]["components"]
                if c["status"] == "insufficient"
            ]
            if not missing:
                continue
            need = needs[row["need_ids"][0]]
            count = len(packets.packet(saved.case_id, (need.id,), tuple(receipts)).evidence)
            passages_before[need.id] = count
            gaps.append(
                ResearchGap(
                    need_id=need.id,
                    claim_statement=statements[need.claim_id],
                    need_description=need.description,
                    gap=classify_gap(hits.get(need.id, 0), count),
                    previous_queries=previous.get(need.id, []),
                    missing=missing,
                )
            )
        if not gaps:
            return judgments, receipts

        model = self.models["research"].api_model_id
        try:
            request = build_followup_request(
                gaps,
                prompts_path=PROJECT_ROOT / "config/prompts.yaml",
                maximum_queries=budget.followup_queries,
                model=model,
            )
            body = await meta.complete(request, self.settings.meta_timeout_seconds)
            usage.append(usage_record("followup_planning", model, body.get("usage")))
            planned = parse_followup_response(
                body["choices"][0]["message"]["content"], gaps, budget.followup_queries
            )
        except (ModelResponseFailure, ValueError, KeyError, IndexError, TypeError):
            limitations.append("Follow-up search planning did not complete.")
            return judgments, receipts
        if not planned:
            return judgments, receipts

        gap_kinds = {gap.need_id: gap.gap for gap in gaps}
        followups = []
        for index, item in enumerate(planned, 1):
            search_request = SearchRequest(query=item.text, language=item.language, max_results=3)
            query_id = f"f{index}"
            session.add_followup(
                saved.case_id,
                query_id,
                search_request,
                [item.need_id],
                gap_kinds[item.need_id],
                item.reason,
            )
            followups.append(
                ResearchQuery(id=query_id, request=search_request, need_ids=[item.need_id])
            )
        before = {page: set(ids) for page, ids in page_needs.items()}
        self._search(
            session,
            research,
            saved.case_id,
            followups,
            read_sources,
            page_needs,
            hits,
            budget.max_source_reads + budget.followup_source_reads + match_reads,
            limitations,
            min_score=self.settings.search_min_score,
        )
        # Only new page/need pairs need selection; earlier pairs keep their receipts.
        new_pairs = {
            page: ids - before.get(page, set())
            for page, ids in page_needs.items()
            if ids - before.get(page, set())
        }
        selections = await self._select(
            research, saved.case_id, new_pairs, budget.followup_selection_calls
        )
        usage.extend(
            usage_record("passage_selection", model, s["usage"])
            for s in selections
            if s.get("usage") and not s.get("cached")
        )
        if any(s["status"] not in {"selected", "not_found"} for s in selections):
            limitations.append("Some follow-up sources could not be evaluated for passages.")
        new_receipts = [s["selection_id"] for s in selections if s.get("selection_id")]
        all_receipts = list(dict.fromkeys([*receipts, *new_receipts]))
        improved = [
            item.need_id
            for item in planned
            if len(packets.packet(saved.case_id, (item.need_id,), tuple(all_receipts)).evidence)
            > passages_before[item.need_id]
        ]
        limitations.append(
            f"Searched again for {len(planned)} unsettled research need(s); "
            f"{len(improved)} gained new passages."
        )
        if improved:
            rejudged = await self._judge(
                meta,
                research,
                saved.case_id,
                improved,
                all_receipts,
                budget.followup_judgment_calls,
            )
            usage.extend(
                usage_record("evidence_judgment", self.models["judge"].api_model_id, j["usage"])
                for j in rejudged
                if j.get("usage") and not j.get("cached")
            )
            replacements = {r["need_ids"][0]: r for r in rejudged if r["status"] == "assessed"}
            if len(replacements) < len(rejudged):
                limitations.append(
                    "Some follow-up assessments did not complete; earlier results were kept."
                )
            judgments = [replacements.get(row["need_ids"][0], row) for row in judgments]
        if progress:
            progress("followup_research")
        return judgments, all_receipts

    @staticmethod
    def _report(investigation_id, claims, plan, judgments, research, limitations, receipts):
        sources, evidence, by_claim = {}, {}, {str(c.id): [] for c in claims}
        statements = {str(c.id): c.statement or c.text for c in claims}
        for row in judgments:
            if row["status"] != "assessed":
                limitations.append(f"Evidence assessment did not complete ({row['status']}).")
                for need_id in row["need_ids"]:
                    need = next(n for n in plan.needs if n.id == need_id)
                    by_claim[need.claim_id].append(
                        FindingComponent(
                            description=need.description,
                            status="not_assessed",
                            explanation=report_text(
                                "assessment_failed", statements[need.claim_id], status=row["status"]
                            ),
                            evidence_ids=[],
                        )
                    )
                continue
            result = row["result"]
            packet = JudgmentRepository(research).packet(
                plan.case_id, (result["need_id"],), tuple(receipts)
            )
            for index, component in enumerate(result["components"]):
                refs = []
                relations = {}
                contexts = []
                for citation in result["citations"]:
                    if citation["component_index"] != index:
                        continue
                    page = research.page(citation["page_id"])
                    # Scope source rows to the investigation; cached pages are shared.
                    source_id = stable_uuid("source", f"{investigation_id}:{citation['page_id']}")
                    evidence_id = stable_uuid(
                        "evidence",
                        f"{result['claim_id']}:{citation['page_id']}:{citation['start']}:{citation['end']}",
                    )
                    sources[source_id] = Source(
                        id=source_id,
                        url=citation["source_url"],
                        title=citation["source_url"],
                        content=page["content"],
                    )
                    evidence[evidence_id] = Evidence(
                        id=evidence_id,
                        claim_id=result["claim_id"],
                        source_id=source_id,
                        excerpt=citation["quote"],
                    )
                    refs.append(evidence_id)
                    relations[str(evidence_id)] = citation["relation"]
                if component["status"] == "insufficient":
                    for item in packet.evidence:
                        page = research.page(item.page_id)
                        source_id = stable_uuid("source", f"{investigation_id}:{item.page_id}")
                        evidence_id = stable_uuid(
                            "evidence",
                            f"{result['claim_id']}:{item.page_id}:{item.start}:{item.end}",
                        )
                        sources[source_id] = Source(
                            id=source_id,
                            url=item.source_url,
                            title=item.source_url,
                            content=page["content"],
                        )
                        evidence[evidence_id] = Evidence(
                            id=evidence_id,
                            claim_id=result["claim_id"],
                            source_id=source_id,
                            excerpt=item.quote,
                        )
                        contexts.append(evidence_id)
                by_claim[result["claim_id"]].append(
                    FindingComponent(
                        description=component["description"],
                        status=component["status"],
                        explanation=component["explanation"],
                        evidence_ids=list(dict.fromkeys(refs)),
                        evidence_relations=relations,
                        context_evidence_ids=list(dict.fromkeys(contexts)),
                    )
                )
        for need in plan.needs:
            if need.status != "planned":
                by_claim[need.claim_id].append(
                    FindingComponent(
                        description=need.description,
                        status="not_assessed",
                        explanation=report_text(need.status, statements[need.claim_id]),
                        evidence_ids=[],
                    )
                )
        findings = []
        for claim in claims:
            components = by_claim[str(claim.id)]
            ids = list(
                dict.fromkeys(
                    e for c in components for e in [*c.evidence_ids, *c.context_evidence_ids]
                )
            )
            findings.append(
                Finding(
                    id=stable_uuid("finding", str(claim.id)),
                    claim_id=claim.id,
                    assessment=Assessment.UNRESOLVED,
                    explanation=report_text("claim_wide_unresolved", claim.statement or claim.text),
                    evidence_ids=ids,
                    components=components,
                )
            )
        return InvestigationReport(
            investigation_id=investigation_id,
            mode="meta",
            claims=claims,
            sources=list(sources.values()),
            evidence=list(evidence.values()),
            findings=findings,
            limitations=limitations,
            research_summary=summarize(plan, judgments),
        )
