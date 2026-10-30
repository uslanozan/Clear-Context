"""Bounded text research using saved query, source and judgment receipts."""

import asyncio
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
from clear_context.providers.meta_structured import MetaStructuredProvider
from clear_context.providers.tavily import RetrievalFailure, TavilyKeyless
from clear_context.repositories.judgment import JudgmentRepository
from clear_context.repositories.retrieval import RetrievalRepository, identity
from clear_context.schemas.retrieval import SavedResearchPlan, canonical_source_url
from clear_context.services.evidence_judgment import EvidenceJudgmentService, JudgmentJob
from clear_context.services.passage_selection import PassageSelectionService, SelectionJob
from clear_context.services.query_planning import PlanningClaim
from clear_context.services.retrieval import RetrievalSession, load_retrieval_policy

DEFERRED_EXPLANATIONS = {
    "needs_context": "Not researched: the claim lacks context this detail depends on.",
    "budget_deferred": "Not researched within this investigation's search budget.",
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
    def __init__(self, settings, models, workspace):
        self.settings, self.models, self.workspace = settings, models, workspace

    def run(self, investigation_id, claims, progress=None):
        return asyncio.run(self._run(investigation_id, claims, progress))

    async def _run(self, investigation_id, claims, progress):
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
            maximum_queries=6,
            model=self.models["research"].api_model_id,
        )
        body = await meta.complete(request, self.settings.meta_timeout_seconds)
        usage = [
            usage_record("query_planning", self.models["research"].api_model_id, body.get("usage"))
        ]
        plan = parse_planner_response(
            body["choices"][0]["message"]["content"], planning_claims, 6, profile
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
        tavily = TavilyKeyless(timeout=30)
        limitations = ["Evidence assessments do not establish source reliability."]
        try:
            research.register_plan(saved)
            policy = load_retrieval_policy(PROJECT_ROOT / "config/retrieval.yaml")
            policy = policy.model_copy(update={"max_search_calls": 6, "max_extract_calls": 3})
            session = RetrievalSession(research, tavily, policy)
            page_needs = {}
            seen_sources = set()
            search_complete = True
            for query in saved.queries:
                try:
                    response = session.search(saved.case_id, query.id)
                except RetrievalFailure as error:
                    limitations.append(f"Search stopped: {error.code}.")
                    search_complete = False
                    break
                for hit in response.get("results", []):
                    try:
                        source = identity("s_", canonical_source_url(hit["url"]))
                        if source not in seen_sources:
                            if len(seen_sources) >= 3:
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
            if progress and search_complete:
                progress("retrieve_sources")
            method, selector, selector_limits, system = load_selector(
                PROJECT_ROOT / "config/passage_selectors.yaml", PROJECT_ROOT / "config/prompts.yaml"
            )
            selector_limits = selector_limits.model_copy(update={"max_model_calls": 3})
            selection_service = PassageSelectionService(
                research,
                MetaPassageProvider(self.settings),
                method,
                selector,
                selector_limits,
                system,
                self.models["research"],
            )
            selections = await selection_service.select_pages(
                [
                    SelectionJob(saved.case_id, page, tuple(sorted(ids)))
                    for page, ids in page_needs.items()
                    if ids
                ]
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
            judge_method, limits, judge_prompt, contract = load_judge(
                PROJECT_ROOT / "config/judges.yaml",
                PROJECT_ROOT / "config/prompts.yaml",
                method="need_components_v2",
            )
            limits = limits.model_copy(update={"max_model_calls": 6})
            judge = EvidenceJudgmentService(
                JudgmentRepository(research),
                meta,
                judge_method,
                limits,
                judge_prompt,
                self.models["judge"],
                response_contract=contract,
            )
            active = [n for n in saved.needs if n.status == "planned"]
            judgments = await judge.assess(
                [JudgmentJob(saved.case_id, (n.id,), tuple(receipts)) for n in active]
            )
            if progress and all(j["status"] == "assessed" for j in judgments):
                progress("assess_components")
            usage.extend(
                usage_record("evidence_judgment", self.models["judge"].api_model_id, j["usage"])
                for j in judgments
                if j.get("usage") and not j.get("cached")
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
                    source_id = stable_uuid("source", citation["page_id"])
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
                        source_id = stable_uuid("source", item.page_id)
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
