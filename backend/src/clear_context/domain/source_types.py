"""Label a source by the kind of site it comes from.

The label tells the evidence assessment where a passage was published; it is not a judgment
of accuracy. Lists are deliberately short and match a domain or any of its subdomains.
"""

from typing import Literal
from urllib.parse import urlsplit

SourceType = Literal["fact_check", "reference", "social", "web"]

FACT_CHECK_HOSTS = (
    "dogrulukpayi.com",
    "teyit.org",
    "dogrula.org",
    "malumatfurus.org",
    "snopes.com",
    "factcheck.afp.com",
    "fullfact.org",
    "politifact.com",
    "factcheck.org",
    "leadstories.com",
    "boomlive.in",
    "altnews.in",
    "factly.in",
    "misbar.com",
    "maldita.es",
    "newtral.es",
    "correctiv.org",
)
# Posts, comments and user-edited forums: anyone can publish there.
SOCIAL_HOSTS = (
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "threads.net",
    "tiktok.com",
    "youtube.com",
    "reddit.com",
    "linkedin.com",
    "pinterest.com",
    "quora.com",
    "telegram.org",
    "t.me",
    "vk.com",
    "9gag.com",
    "eksisozluk.com",
    "medium.com",
    "blogspot.com",
    "wordpress.com",
    "livejournal.com",
    "tumblr.com",
)
REFERENCE_HOSTS = (
    "wikipedia.org",
    "wikimedia.org",
    "britannica.com",
    "unesco.org",
    "archive.org",
    "loc.gov",
)
# Government and academic domains, including country-coded ones such as gov.tr or ac.uk.
REFERENCE_LABELS = {"gov", "edu", "mil", "int", "ac"}


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def on_host(url: str, hosts: tuple[str, ...]) -> bool:
    host = host_of(url)
    return any(host == name or host.endswith("." + name) for name in hosts)


def classify_source(url: str) -> SourceType:
    # Fact-check sections of larger sites are listed by path.
    if on_host(url, FACT_CHECK_HOSTS) or "/fact-check" in url or "/factcheck" in url:
        return "fact_check"
    if on_host(url, SOCIAL_HOSTS):
        return "social"
    labels = host_of(url).split(".")
    if on_host(url, REFERENCE_HOSTS) or REFERENCE_LABELS & set(labels[-2:]):
        return "reference"
    return "web"
