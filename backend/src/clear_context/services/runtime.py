"""Providers built from one set of effective settings.

A saved settings change builds a new Runtime; investigations already running keep the one they
started with, and its HTTP clients close when the last of them finishes.
"""

import threading
from dataclasses import dataclass, field
from pathlib import Path

from clear_context.core.prompts import load_claim_extraction_prompt
from clear_context.core.settings import (
    ModelSelection,
    Settings,
    load_model_selections,
    resolve_path,
)
from clear_context.providers.base import InvestigationProvider
from clear_context.providers.fact_check import build_fact_check_search
from clear_context.providers.link_reader import build_link_reader
from clear_context.providers.meta import MetaInvestigationProvider
from clear_context.providers.meta_media import MetaMediaAnalyzer, MockMediaAnalyzer
from clear_context.providers.mock import MockInvestigationProvider
from clear_context.providers.reverse_image import build_reverse_image_search
from clear_context.services.investigation_research import InvestigationResearch


@dataclass
class Runtime:
    settings: Settings = field(repr=False)
    models: dict[str, ModelSelection]
    provider: InvestigationProvider = field(repr=False)
    media_analyzer: object = field(repr=False)
    reverse_image: object | None = field(default=None, repr=False)
    fact_checks: object | None = field(default=None, repr=False)
    link_reader: object | None = field(default=None, repr=False)
    research: InvestigationResearch | None = field(default=None, repr=False)
    users: int = 0
    retired: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def mode(self) -> str:
        return self.settings.app_mode

    @property
    def live(self) -> bool:
        return self.settings.app_mode == "meta" and self.settings.allow_paid_api_calls

    @property
    def research_enabled(self) -> bool:
        return self.research is not None

    def acquire(self) -> "Runtime":
        with self.lock:
            self.users += 1
        return self

    def release(self) -> None:
        with self.lock:
            self.users -= 1
            done = self.retired and self.users == 0
        if done:
            self.close()

    def retire(self) -> None:
        """Close once no running investigation uses this runtime any more."""
        with self.lock:
            self.retired = True
            done = self.users == 0
        if done:
            self.close()

    def close(self) -> None:
        for client in (self.reverse_image, self.fact_checks, self.link_reader):
            if client is not None:
                client.close()


def build_runtime(settings: Settings, research_workspace: Path) -> Runtime:
    """Build every provider; raises ValueError when the settings cannot run."""
    models = load_model_selections(settings)
    prompt = load_claim_extraction_prompt(settings)
    provider = (
        MetaInvestigationProvider(settings, models["claim_extraction"], prompt=prompt)
        if settings.app_mode == "meta"
        else MockInvestigationProvider()
    )
    live = settings.app_mode == "meta" and settings.allow_paid_api_calls
    media_analyzer = (
        MetaMediaAnalyzer(
            settings, models["screenshot"], resolve_path(settings.prompt_catalog_path)
        )
        if live
        else MockMediaAnalyzer()
    )
    research = (
        InvestigationResearch(settings, models, research_workspace)
        if settings.app_mode == "meta" and settings.research_enabled
        else None
    )
    # Preview mode makes no external calls: no reverse image search, fact checks or links.
    return Runtime(
        settings=settings,
        models=models,
        provider=provider,
        media_analyzer=media_analyzer,
        reverse_image=build_reverse_image_search(settings) if live else None,
        fact_checks=build_fact_check_search(settings) if live else None,
        # Links are read through Tavily, like research sources.
        link_reader=build_link_reader(settings) if live and settings.link_reading else None,
        research=research,
    )
