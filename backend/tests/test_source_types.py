from uuid import uuid4

from clear_context.core.judges import load_judge
from clear_context.core.settings import PROJECT_ROOT, Settings
from clear_context.domain.investigation import Source
from clear_context.domain.source_types import classify_source


def test_sources_are_labeled_by_site_kind():
    assert classify_source("https://www.dogrulukpayi.com/dogruluk-kontrolu/a") == "fact_check"
    assert classify_source("https://www.usatoday.com/story/news/factcheck/2020/a") == "fact_check"
    assert classify_source("https://www.facebook.com/page/videos/1") == "social"
    assert classify_source("https://x.com/user/status/1") == "social"
    assert classify_source("https://mosat.blogspot.com/2011/07/a.html") == "social"
    assert classify_source("https://en.wikipedia.org/wiki/Kabul") == "reference"
    assert classify_source("https://www.ktb.gov.tr/a") == "reference"
    assert classify_source("https://www.ox.ac.uk/a") == "reference"
    assert classify_source("https://petapixel.com/2025/a") == "web"
    # A look-alike domain is not the listed site.
    assert classify_source("https://notfacebook.com/a") == "web"


def test_stored_sources_get_their_label_from_the_url():
    source = Source(id=uuid4(), url="https://x.com/a/status/1", title="Post", content="Text")
    assert source.source_type == "social"


def test_default_judge_appends_the_source_rule_to_v4():
    settings = Settings(_env_file=None)
    method, _, system, contract = load_judge(
        PROJECT_ROOT / "config/judges.yaml",
        PROJECT_ROOT / "config/prompts.yaml",
        method=settings.research_judge_profile,
    )
    assert (method, contract) == ("need_components_v5", "components_v3")
    assert system.startswith("The claim field is the claim exactly as stated.")
    assert "only repeats or" in system and "source_type" in system


def test_judge_request_carries_each_passage_source_type():
    from clear_context.providers.meta_judgment import build_judgment_request

    class Need:
        id, claim_id, description = "n1", "c1", "Only two cars existed in Ohio in 1895"

    class Claim:
        id, statement = "c1", "In 1895 Ohio had only two cars."

    class Evidence:
        id, quote = "e_1", "In 1895 Ohio had only two cars."
        source_url = "https://www.facebook.com/page/videos/1"

    class Packet:
        needs, claims, evidence = [Need], [Claim], [Evidence]

    import json

    from clear_context.providers import meta_judgment

    original = meta_judgment.evidence_aliases
    meta_judgment.evidence_aliases = lambda packet: {"E1": "e_1"}
    original_parent = meta_judgment.parent_claim
    meta_judgment.parent_claim = lambda packet: Claim.statement
    try:
        request = build_judgment_request(
            "system", Packet, "muse-spark-1.3", "low", 100, "components_v3"
        )
    finally:
        meta_judgment.evidence_aliases = original
        meta_judgment.parent_claim = original_parent
    evidence = json.loads(request["messages"][1]["content"])["evidence"]
    assert evidence == [{"id": "E1", "text": Evidence.quote, "source_type": "social"}]
