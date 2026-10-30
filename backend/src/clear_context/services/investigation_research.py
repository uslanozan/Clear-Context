"""Bounded text research using saved query, source and judgment receipts."""

import asyncio
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

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
    Source,
)
from clear_context.providers.meta_passages import MetaPassageProvider
from clear_context.providers.meta_structured import MetaStructuredProvider, ModelResponseFailure
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
from clear_context.services.passage_selection import PassageSelectionService, SelectionJob
from clear_context.services.query_planning import PlanningClaim
from clear_context.services.retrieval import RetrievalSession, load_retrieval_policy

DEFERRED_EXPLANATIONS = {
    "needs_context": "Not researched: the claim lacks context this detail depends on.",
    "budget_deferred": "Not researched within this investigation's search budget.",
}


@dataclass(frozen=True)
class ResearchBudget:
    """Per-investigation call limits; research modes vary these, not the methods."""

    max_queries: int = 6
    max_source_reads: int = 3
    max_selection_calls: int = 3
    max_judgment_calls: int = 6
    # One follow-up round for needs left insufficient; 0 disables it.
    followup_queries: int = 2
    followup_source_reads: int = 2
    followup_selection_calls: int = 3
    followup_judgment_calls: int = 2


RESEARCH_MODES = {
    "fast": ResearchBudget(
        max_queries=3,
        max_source_reads=2,
        max_selection_calls=2,
        max_judgment_calls=4,
        followup_queries=0,
        followup_source_reads=0,
        followup_selection_calls=0,
        followup_judgment_calls=0,
    ),
    "balanced": ResearchBudget(),
    "deep": ResearchBudget(
        max_queries=10,
        max_source_reads=5,
        max_selection_calls=5,
        max_judgment_calls=10,
        followup_queries=4,
        followup_source_reads=3,
        followup_selection_calls=4,
        followup_judgment_calls=4,
    ),
}


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

    def run(self, investigation_id, claims, progress=None, mode=None):
        budget = RESEARCH_MODES[mode] if mode else self.budget
        return asyncio.run(self._run(investigation_id, claims, progress, budget))

    async def _run(self, investigation_id, claims, progress, budget):
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
        request, profile = build_planner_request(
            planning_claims,
            planners_path=PROJECT_ROOT / "config/query_planners.yaml",
            prompts_path=PROJECT_ROOT / "config/prompts.yaml",
            source_language="auto",
            maximum_queries=budget.max_queries,
            model=self.models["research"].api_model_id,
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
                    "max_extract_calls": budget.max_source_reads + budget.followup_source_reads,
                    "max_followup_queries": budget.followup_queries,
                }
            )
            session = RetrievalSession(research, tavily, policy)
            page_needs, hits, seen_sources = {}, {}, set()
            search_complete = self._search(
                session,
                research,
                saved.case_id,
                saved.queries,
                seen_sources,
                page_needs,
                hits,
                budget.max_source_reads,
                limitations,
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
                    seen_sources,
                    limitations,
                    usage,
                    progress,
                    budget,
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
    def _search(
        session,
        research,
        case_id,
        queries,
        seen_sources,
        page_needs,
        hits,
        source_limit,
        limitations,
    ):
        """Run queries and read new sources up to source_limit; False if search stopped."""
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
                try:
                    source = identity("s_", canonical_source_url(hit["url"]))
                    if source not in seen_sources:
                        if len(seen_sources) >= source_limit:
                            if "Source read budget reached." not in limitations:
                                limitations.append("Source read budget reached.")
                            continue
                        seen_sources.add(source)
                        page = session.read_source(source)
                        page_needs[page] = set()
                    else:
                        page = next(
                            (
                                pid
                                for pid in page_needs
                                if research.page(pid)["source_id"] == source
                            ),
                            None,
                        )
                    if page:
                        page_needs[page].update(query.need_ids)
                except (RetrievalFailure, ValueError, KeyError) as error:
                    code = getattr(error, "code", "invalid_source")
                    limitations.append(f"A source could not be read ({code}).")
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
            method="need_components_v2",
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
        seen_sources,
        limitations,
        usage,
        progress,
        budget,
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
            seen_sources,
            page_needs,
            hits,
            budget.max_source_reads + budget.followup_source_reads,
            limitations,
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
        for row in judgments:
            if row["status"] != "assessed":
                limitations.append(f"Evidence assessment did not complete ({row['status']}).")
                for need_id in row["need_ids"]:
                    need = next(n for n in plan.needs if n.id == need_id)
                    by_claim[need.claim_id].append(
                        FindingComponent(
                            description=need.description,
                            status="not_assessed",
                            explanation=(
                                f"Evidence assessment did not complete ({row['status']}); "
                                "this detail was not evaluated."
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
                        explanation=DEFERRED_EXPLANATIONS[need.status],
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
                    explanation="Claim-wide coverage is not established; review each detail below.",
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
        )
