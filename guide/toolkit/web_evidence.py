"""Newsroom: recent public context from Amazon Bedrock AgentCore Web Search, as Exhibits.

Web Exhibits are Context evidence. They never change a Hard_Rule, a computed number, or
the maximum weight: those come only from the pinned Dataset_Snapshot. Each result keeps
its title, URL and publication date, because the Web Search acceptable-use terms require
every surfaced result to show its source citation and link.
"""
from __future__ import annotations

import re
import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from guide.toolkit.exhibits import Exhibit, ExhibitRegistry

WEB_SEARCH_ID = "web-search.v1"
WEB_METRIC = "web_news"
CONFIDENCE = "Context"
SNIPPET_MAX_CHARS = 600

# News and controversies: wire services, business media, general press and regulators.
NEWS_DOMAINS: tuple[str, ...] = (
    "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "wsj.com", "cnbc.com", "marketwatch.com",
    "barrons.com", "morningstar.com", "finance.yahoo.com", "businessinsider.com", "theverge.com",
    "techcrunch.com", "bbc.com", "theguardian.com", "nytimes.com", "washingtonpost.com", "cnn.com",
    "cbc.ca", "theglobeandmail.com", "bnnbloomberg.ca", "financialpost.com", "lapresse.ca",
    "sec.gov", "sedarplus.ca", "bankofcanada.ca", "federalreserve.gov", "epa.gov", "justice.gov",
)
# Results and guidance: issuers' own releases and newswires, plus the press above.
ISSUER_DOMAINS: tuple[str, ...] = (
    "businesswire.com", "newswire.ca", "prnewswire.com", "globenewswire.com",
    "ir.tesla.com", "nvidianews.nvidia.com", "investor.nvidia.com", "investor.apple.com",
    "microsoft.com", "abc.xyz", "ir.aboutamazon.com", "jpmorganchase.com", "jnj.com", "pginvestor.com",
    "investor.exxonmobil.com", "corporate.exxonmobil.com", "rbc.com", "td.com", "manulife.com",
    "enbridge.com", "cnrl.com", "cn.ca", "fortisinc.com", "corpo.couche-tard.com", "shopify.com",
    "csisoftware.com",
)
TRUSTED_DOMAINS: tuple[str, ...] = NEWS_DOMAINS + ISSUER_DOMAINS
# Rating and price-target aggregators (opinions about future prices) are left out on purpose.

_GENERIC_TITLE = re.compile(r"investor relations|^home\b|stock (?:price|quote)|\(\w{1,5}\)\s*$", re.I)


# Headlines that are opinions about future prices (forecasts, targets, buy/sell calls, valuation
# pitches). The brief forbids predicting returns, so they never become evidence.
_FORECAST_TITLE = re.compile(
    r"price target|\btarget\b.*\$|\$\d[\d,.]*\s*(?:next year|by 20\d\d)|push past|could (?:soar|surge|double|"
    r"triple|crash|plunge)|\bto (?:soar|surge|double|crash)\b|undervalued|overvalued|\b(?:buy|sell) (?:rating|now)\b|"
    r"reaffirms .*(?:buy|sell|hold)|upgrade[sd]?\b|downgrade[sd]?\b|should you buy|is it time to buy|"
    r"stock to buy|best stocks?|millionaire|you'?d now need|shares of .* you'?d|bull case|bear case|forecast|prediction|"
    r"worth buying|buy the dip|time to (?:buy|sell)|\bbuy or sell\b|\b(?:a )?(?:buy|sell|hold)\?",
    re.I)


# Promotional or retrospective pieces ("If you'd invested $1,000...", "A 68-year-old retiree bought...",
# analyst-blog digests, "stocks to watch" lists): they sell a return story, they do not report an event.
_PROMO_TITLE = re.compile(
    r"\b\d{2}-year-old\b|\bretiree\b|\bif you(?:'d| had| would have)? invested\b|\bbought [\d,]+ shares\b|"
    r"\$[\d,]+ (?:invested|investment)\b|turn(?:ed|s)? (?:her|his|your|a|the) .{0,30}\binto\b|here'?s how much|"
    r"every move|analyst blog|blog highlights|tech radar|stocks? to watch|\b\d+ (?:stocks|reasons|things)\b|"
    r"\bmy (?:portfolio|stake|shares)\b|\bpassive income\b|\bretire (?:early|rich)\b",
    re.I)
MAX_PER_SOURCE = 2


def is_informative(title: str) -> bool:
    """Drop landing pages (e.g. 'Tesla Investor Relations'), price forecasts or buy/sell calls, and
    promotional or retrospective-return pieces."""
    return (len(title.split()) >= 5 and not _GENERIC_TITLE.search(title)
            and not _FORECAST_TITLE.search(title) and not _PROMO_TITLE.search(title))


def mentions_subject(title: str, ticker: str, name: str) -> bool:
    """The headline must be about the asset: its ticker or a distinctive word of its name."""
    if not ticker and not name:
        return True
    words = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z&.'-]{2,}", name or "")
             if w.lower() not in {"inc", "corp", "corporation", "the", "group", "holdings", "company", "ltd"}}
    base = (ticker or "").split(".")[0].lower()
    tokens = {t.lower() for t in re.findall(r"[A-Za-z]+", title)}
    return bool(base and base in tokens) or bool(words & tokens)


# Page furniture that search snippets often carry: market tickers, nav bars, ad labels, tables.
_SNIPPET_JUNK = re.compile(
    r"\badvertisement\b|\bquick read\b|\brates commodities currencies\b|\bu\.?s\.? markets? (?:closed|open)\b|"
    r"\btrending\b|\bsign in\b|\bsubscribe\b|\bread more\b|\bskip to\b|\bexplore stocks\b|"
    r"\btrading disclosure\b|\bon coinbase\b",
    re.I)
_QUOTE_RUN = re.compile(r"(?:[\^]?[A-Z]{2,6}\s+)?[-+]?\d[\d,.]*%?(?:\s+[-+]?\d[\d,.]*%?){1,}")


def clean_snippet(text: str, limit: int = 300) -> str:
    """Keep the readable sentences of a snippet: no tables, quote strips or page furniture.
    Each removed piece becomes a break, so a fragment of navigation never joins a real sentence.
    Returns "" when nothing readable is left (the card then shows the headline alone)."""
    brk = " \u00b6 "
    text = " ".join(str(text or "").split())
    if "|" in text:
        text = brk.join(part for part in text.split("|") if len(part.split()) >= 6)
    text = _SNIPPET_JUNK.sub(brk, text)
    text = re.sub(r"\s[\u00b7\u2022]\s|\b(?:Senior |Staff )?(?:Reporter|Writer|Editor|Correspondent)\b", brk, text)
    text = re.sub(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+(?:[A-Z][a-z]+\s+)?(?:\d{1,2},?\s+)?(?:\d{4},?\s+)?"
                  r"(?:at\s+)?\d{1,2}:\d{2}\s*(?:[AP]\.?M\.?)?(?:\s+[A-Z]{2,4}\b)?\.?", brk, text)  # datelines
    text = re.sub(r"[\^]\w+", brk, text)
    text = re.sub(r"(?:\b[A-Z]{2,6}\b\s+){2,}", brk, text)  # runs of tickers: "SPCX TSLA"
    text = _QUOTE_RUN.sub(brk, text)
    segments = [" ".join(seg.split()).strip(" -\u2014:;,") for seg in text.split("\u00b6")]
    segments = [seg for seg in segments if len(seg.split()) >= 6]
    kept: list[str] = []
    for i, segment in enumerate(segments):
        sentences = re.split(r"(?<=[a-z0-9)%][.!?])\s+(?=[A-Z\"\u201c(])", segment)
        for j, sentence in enumerate(sentences):
            words = sentence.split()
            letters = sum(c.isalpha() for c in sentence)
            complete = sentence.rstrip().endswith((".", "!", "?", "\"", "\u201d", ")"))
            # The search engine may cut the last sentence: keep that tail if it is long enough.
            tail = i == len(segments) - 1 and j == len(sentences) - 1 and len(words) >= 10
            if len(words) >= 6 and letters >= 0.6 * max(len(sentence), 1) and (complete or tail):
                kept.append(sentence if complete else sentence.rsplit(" ", 1)[0].rstrip(",;: ") + "\u2026")
            if len(" ".join(kept)) >= limit:
                break
        if len(" ".join(kept)) >= limit:
            break
    out = " ".join(kept)
    if len(out) > limit:
        out = out[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return out


ESG_KEYWORDS = "controversy lawsuit environmental spill fine"


_SECOND_LEVEL = {"co.uk", "com.au", "co.jp", "com.br", "co.in"}


def _domain(url: str) -> str:
    """The site, not the server: 'ca.finance.yahoo.com' -> 'finance.yahoo.com' when that is the
    trusted entry, else the registrable domain ('kessler-prod.x.morningstar.com' -> 'morningstar.com')."""
    host = (urlparse(url).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    for trusted in TRUSTED_DOMAINS:
        if host == trusted:
            return trusted
    for trusted in sorted(TRUSTED_DOMAINS, key=len, reverse=True):
        base = ".".join(trusted.split(".")[-2:])
        if host.endswith("." + trusted) or (host.endswith("." + base) and trusted == base):
            return trusted
    parts = host.split(".")
    keep = 3 if ".".join(parts[-2:]) in _SECOND_LEVEL else 2
    return ".".join(parts[-keep:])


def _site(source: str) -> str:
    """The registrable domain used to cap articles per site (finance.yahoo.com -> yahoo.com)."""
    parts = source.split(".")
    keep = 3 if ".".join(parts[-2:]) in _SECOND_LEVEL else 2
    return ".".join(parts[-keep:])


def _published(raw: Any, fallback: date) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    return fallback


def build_queries(ticker: str, name: str, contract: Mapping[str, Any]) -> list[tuple[str, tuple[str, ...]]]:
    """2 or 3 searches, each with its source list: news (press), results/guidance (issuer and
    press), and controversies (press, regulators) when ESG matters to the investor."""
    label = f"{name} {ticker.split('.')[0]}".strip()
    queries = [(f"{label} news", NEWS_DOMAINS), (f"{label} quarterly results guidance", TRUSTED_DOMAINS)]
    esg = bool(contract.get("esg_exclusions")) or any(
        "esg" in str(p.get("id", "")).lower() or "esg" in str(p.get("text", "")).lower()
        for p in (contract.get("soft_preferences") or []) if isinstance(p, Mapping))
    if esg:
        queries.append((f"{label} {ESG_KEYWORDS}", NEWS_DOMAINS))
    return [(q[:200], d) for q, d in queries]


class Newsroom:
    """Runs bounded web searches for one session and records each result as a Web Exhibit."""

    def __init__(
        self,
        search: Callable[..., Mapping[str, Any]],
        *,
        max_results: int = 4,
        days: int = 30,
        domains: Sequence[str] = TRUSTED_DOMAINS,
        max_exhibits: int = 6,
        max_agent_searches: int = 2,
        now: Callable[[], datetime] | None = None,
        screen: Callable[[str], bool] | None = None,
    ) -> None:
        self._search = search
        self._screen = screen
        self.max_results = max_results
        self.days = days
        self.domains = list(domains)
        self.max_exhibits = max_exhibits
        self.max_agent_searches = max_agent_searches
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._seen: set[str] = set()
        self._per_source: dict[str, int] = {}
        self._subject: tuple[str, str] = ("", "")
        self._agent_searches = 0
        self._lock = threading.Lock()
        self.failures: list[str] = []

    @classmethod
    def from_config(cls, config: Any, client: Any | None = None) -> "Newsroom":
        if client is None:
            import boto3
            from botocore.config import Config as BotoConfig
            timeout = float(getattr(config, "web_search_timeout_seconds", 6))
            client = boto3.client("bedrock-agentcore", region_name=config.aws_region,
                                  config=BotoConfig(connect_timeout=timeout, read_timeout=timeout,
                                                    retries={"max_attempts": 1}))
        return cls(client.invoke_web_search,
                   max_results=int(getattr(config, "web_search_max_results", 4)),
                   days=int(getattr(config, "web_search_days", 30)),
                   screen=guardrail_screen(config))

    # ---- search ----
    def _call(self, query: str, domains: Sequence[str] | None = None) -> list[dict[str, Any]]:
        now = self._now()
        after = (now - timedelta(days=self.days)).strftime("%Y-%m-%dT00:00:00Z")
        before = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        response = self._search(
            webSearchId=WEB_SEARCH_ID,
            searchQuery=query[:200],
            maxResults=self.max_results,
            filters={"domainFilter": {"include": list(domains or self.domains)[:100]},
                     "publishedDateFilter": {"publishedAfter": after, "publishedBefore": before}},
        )
        return [dict(r) for r in (response.get("results") or []) if isinstance(r, Mapping)]

    def _record(self, registry: ExhibitRegistry, ticker: str, query: str,
                result: Mapping[str, Any], origin: str) -> Exhibit | None:
        url = str(result.get("url") or "").strip()
        title = re.sub(r"^[^:]{1,40}\s:\s+", "", str(result.get("title") or "").strip())
        if not url.startswith(("http://", "https://")) or not title or not is_informative(title):
            return None
        if not mentions_subject(title, ticker or self._subject[0], self._subject[1]):
            return None
        source = _domain(url)
        with self._lock:
            if url in self._seen or len(self._seen) >= self.max_exhibits:
                return None
            site = _site(source)
            if self._per_source.get(site, 0) >= MAX_PER_SOURCE:
                return None
            self._seen.add(url)
            self._per_source[site] = self._per_source.get(site, 0) + 1
        snippet_text = f"{title}: {result.get('text') or ''}"
        if self._screen is not None:
            try:
                safe = self._screen(snippet_text)
            except Exception as error:  # screening unavailable: keep the result, record why
                self.failures.append(f"screen: {type(error).__name__}")
                safe = True
            if not safe:
                self.failures.append(f"screened out by Guardrail: {url}")
                return None
        now = self._now()
        published = _published(result.get("publishedAt") or result.get("publishedDate"), now.date())
        snippet = clean_snippet(str(result.get("text") or ""))[:SNIPPET_MAX_CHARS]
        retrieved = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        return registry.add(
            metric=WEB_METRIC,
            value={"title": title, "url": url, "source": source,
                   "published": published.isoformat(), "snippet": snippet,
                   "retrieved_at": retrieved, "confidence": CONFIDENCE, "origin": origin},
            period_start=published,
            period_end=published,
            assets=(ticker,),
            currency="n/a",
            source_files=(url,),
            processing_notes=(
                f"Amazon Bedrock AgentCore Web Search ({WEB_SEARCH_ID}), retrieved {retrieved}",
                "Context only: not used by any Hard_Rule, number, or maximum weight",
                "Published after or near the Dataset_Snapshot end; not a forecast",
            ),
            inputs={"query": query, "days": self.days, "origin": origin},
        )

    def collect(self, registry: ExhibitRegistry, ticker: str, name: str,
                contract: Mapping[str, Any], trace: Any | None = None) -> list[Exhibit]:
        """Code-run searches for the requested asset. A failure is recorded, never fatal."""
        self._subject = (ticker, name)
        found: list[Exhibit] = []
        for query, domains in build_queries(ticker, name, contract):
            try:
                results = self._call(query, domains)
            except Exception as error:  # network, permission, throttling: the session goes on
                self.failures.append(f"{query}: {type(error).__name__}")
                if trace is not None:
                    trace.judge_check("web_search", {"query": query}, f"failed: {type(error).__name__}")
                continue
            kept = [ex for r in results if (ex := self._record(registry, ticker, query, r, "code"))]
            found += kept
            if trace is not None:
                trace.judge_check("web_search", {"query": query, "results": len(results)},
                                  {"exhibits": [e.number for e in kept]})
        return found

    def agent_search(self, registry: ExhibitRegistry, query: str, ticker: str = "") -> dict[str, Any]:
        """The Investigator's web_search tool: bounded follow-up searches."""
        with self._lock:
            if self._agent_searches >= self.max_agent_searches:
                return {"status": "error", "content": [{"json": {
                    "code": "limit_reached", "message": f"at most {self.max_agent_searches} web searches"}}]}
            self._agent_searches += 1
        query = str(query or "").strip()
        if not query:
            return {"status": "error", "content": [{"json": {"code": "invalid_argument",
                                                             "message": "query is required"}}]}
        try:
            results = self._call(query, NEWS_DOMAINS)
        except Exception as error:
            self.failures.append(f"{query}: {type(error).__name__}")
            return {"status": "error", "content": [{"json": {"code": "web_search_failed",
                                                             "message": type(error).__name__}}]}
        exhibits = [ex for r in results if (ex := self._record(registry, ticker, query, r, "investigator"))]
        return {"status": "success",
                "content": [{"json": {"web_exhibits": [context_entry(e) for e in exhibits]}}]}


def context_entry(exhibit: Exhibit) -> dict[str, Any]:
    """What agents see of a Web Exhibit."""
    v = exhibit.value
    return {"exhibit": exhibit.number, "title": v["title"], "source": v["source"], "url": v["url"],
            "published": v["published"], "snippet": v["snippet"], "confidence": CONFIDENCE}


def web_context(registry: ExhibitRegistry) -> list[dict[str, Any]]:
    return [context_entry(e) for e in registry.all() if e.metric == WEB_METRIC]


def guardrail_screen(config: Any) -> Callable[[str], bool] | None:
    """Scan retrieved web text with the Bedrock Guardrail (prompt-attack filter) before agents see it."""
    guardrail_id = str(getattr(config, "guardrail_id", "") or "").strip()
    if not guardrail_id:
        return None
    import boto3
    client = boto3.client("bedrock-runtime", region_name=config.aws_region)

    def screen(text: str) -> bool:
        response = client.apply_guardrail(
            guardrailIdentifier=guardrail_id, guardrailVersion=config.guardrail_version,
            source="INPUT", content=[{"text": {"text": text[:5000]}}])
        return response.get("action") != "GUARDRAIL_INTERVENED"
    return screen


def guard_text(entries: Sequence[Mapping[str, Any]]) -> str:
    """Retrieved web text, scanned by the Guardrail prompt-attack filter (guardContent)."""
    return "\n".join(f"{e.get('title', '')}: {e.get('snippet', '')}" for e in entries)[:8000]


WEB_SEARCH_TOOL_SPEC = {"toolSpec": {
    "name": "web_search",
    "description": ("Search recent public web news (last 30 days, trusted sources) about an asset or event. "
                    "Each result becomes a Web Exhibit (Context only) with title, source, date and link. "
                    "Use for events (recall, lawsuit, guidance, regulation), never for price forecasts."),
    "inputSchema": {"json": {"type": "object", "additionalProperties": False, "required": ["query"],
                             "properties": {"query": {"type": "string", "description": "at most 200 characters"},
                                            "ticker": {"type": "string"}}}},
}}


class WebToolRunner:
    """Toolkit tools plus the bounded web_search tool (for the Investigator)."""

    def __init__(self, base: Any, newsroom: Newsroom, registry: ExhibitRegistry) -> None:
        self.base, self.newsroom, self.registry = base, newsroom, registry

    @property
    def tool_config(self) -> dict[str, Any]:
        base = self.base.tool_config() if callable(getattr(self.base, "tool_config", None)) \
            else dict(getattr(self.base, "tool_config", {}) or {"tools": []})
        return {"tools": list(base.get("tools", [])) + [WEB_SEARCH_TOOL_SPEC]}

    def run(self, tool_use: Mapping[str, Any]) -> dict[str, Any]:
        if tool_use.get("name") == "web_search":
            raw = tool_use.get("input") or {}
            return self.newsroom.agent_search(self.registry, str(raw.get("query", "")),
                                              str(raw.get("ticker", "")))
        return self.base.run(tool_use)

    __call__ = run
