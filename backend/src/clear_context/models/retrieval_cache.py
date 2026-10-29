"""Tables for an isolated, rebuildable research workspace."""

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()
cases = Table(
    "research_cases",
    metadata,
    Column("id", String, primary_key=True),
    Column("plan", Text, nullable=False),
)
claims = Table(
    "research_claims",
    metadata,
    Column("case_id", String, ForeignKey("research_cases.id"), primary_key=True),
    Column("id", String, primary_key=True),
)
needs = Table(
    "research_needs",
    metadata,
    Column("case_id", String, primary_key=True),
    Column("id", String, primary_key=True),
    Column("claim_id", String, nullable=False),
    ForeignKeyConstraint(
        ["case_id", "claim_id"], ["research_claims.case_id", "research_claims.id"]
    ),
)
queries = Table(
    "research_queries",
    metadata,
    Column("case_id", String, ForeignKey("research_cases.id"), primary_key=True),
    Column("id", String, primary_key=True),
    Column("payload", Text, nullable=False),
    Column("origin", String, nullable=False),
)
query_needs = Table(
    "research_query_needs",
    metadata,
    Column("case_id", String, primary_key=True),
    Column("query_id", String, primary_key=True),
    Column("need_id", String, primary_key=True),
    ForeignKeyConstraint(
        ["case_id", "query_id"], ["research_queries.case_id", "research_queries.id"]
    ),
    ForeignKeyConstraint(["case_id", "need_id"], ["research_needs.case_id", "research_needs.id"]),
)
sources = Table(
    "research_sources",
    metadata,
    Column("id", String, primary_key=True),
    Column("url", Text, nullable=False, unique=True),
)
hits = Table(
    "research_hits",
    metadata,
    Column("case_id", String, primary_key=True),
    Column("query_id", String, primary_key=True),
    Column("source_id", String, ForeignKey("research_sources.id"), primary_key=True),
    Column("rank", Integer, nullable=False),
    Column("result", Text, nullable=False),
    Column("retrieved_at", Float, nullable=False),
    ForeignKeyConstraint(
        ["case_id", "query_id"], ["research_queries.case_id", "research_queries.id"]
    ),
)
cache = Table(
    "research_cache",
    metadata,
    Column("kind", String, primary_key=True),
    Column("key", String, primary_key=True),
    Column("payload", Text, nullable=False),
    Column("fetched_at", Float, nullable=False),
    Column("expires_at", Float, nullable=False),
)
pages = Table(
    "research_pages",
    metadata,
    Column("id", String, primary_key=True),
    Column("source_id", String, ForeignKey("research_sources.id"), nullable=False),
    Column("content", Text, nullable=False),
    Column("fetched_at", Float, nullable=False),
)
passages = Table(
    "research_passages",
    metadata,
    Column("id", String, primary_key=True),
    Column("page_id", String, ForeignKey("research_pages.id"), nullable=False),
    Column("start", Integer, nullable=False),
    Column("end", Integer, nullable=False),
    Column("quote", Text, nullable=False),
)
passage_needs = Table(
    "research_passage_needs",
    metadata,
    Column("passage_id", String, ForeignKey("research_passages.id"), primary_key=True),
    Column("case_id", String, primary_key=True),
    Column("need_id", String, primary_key=True),
    ForeignKeyConstraint(["case_id", "need_id"], ["research_needs.case_id", "research_needs.id"]),
)
events = Table(
    "research_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("at", Float, nullable=False),
    Column("kind", String, nullable=False),
    Column("payload", Text, nullable=False),
)

selections = Table(
    "research_selections",
    metadata,
    Column("id", String, primary_key=True),
    Column("case_id", String, ForeignKey("research_cases.id"), nullable=False),
    Column("page_id", String, ForeignKey("research_pages.id"), nullable=False),
    Column("method", String, nullable=False),
    Column("model", String, nullable=False),
    Column("prompt_sha256", String, nullable=False),
    Column("request_key", String, nullable=False),
    Column("result", Text, nullable=False),
    Column("created_at", Float, nullable=False),
)
selection_passages = Table(
    "research_selection_passages",
    metadata,
    Column("selection_id", String, ForeignKey("research_selections.id"), primary_key=True),
    Column("passage_id", String, ForeignKey("research_passages.id"), primary_key=True),
    Column("case_id", String, primary_key=True),
    Column("need_id", String, primary_key=True),
    ForeignKeyConstraint(["case_id", "need_id"], ["research_needs.case_id", "research_needs.id"]),
)

judgments = Table(
    "research_judgments",
    metadata,
    Column("id", String, primary_key=True),
    Column("case_id", String, ForeignKey("research_cases.id"), nullable=False),
    Column("method", String, nullable=False),
    Column("model", String, nullable=False),
    Column("request_key", String, nullable=False),
    Column("packet", Text, nullable=False),
    Column("result", Text, nullable=False),
    Column("usage", Text, nullable=False),
    Column("created_at", Float, nullable=False),
)
judgment_selections = Table(
    "research_judgment_selections",
    metadata,
    Column("judgment_id", String, ForeignKey("research_judgments.id"), primary_key=True),
    Column("selection_id", String, ForeignKey("research_selections.id"), primary_key=True),
)
