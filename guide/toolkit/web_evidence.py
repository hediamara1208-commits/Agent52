"""Newsroom: recent public context from Amazon Bedrock AgentCore Web Search, as Exhibits.

Web Exhibits are Context evidence. They never change a Hard_Rule, a computed number, or
the maximum weight: those come only from the pinned Dataset_Snapshot. Each result keeps
its title, URL and publication date, because the Web Search acceptable-use terms require
every surfaced result to show its source citation and link.
"""
from __future__ import annotations

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

# Primary and reputable sources. Aggregators that mostly relay ratings and price
# targets (opinions about future prices) are left out on purpose.
TRUSTED_DOMAINS: tuple[str, ...] = (
    "reuters.com", "apnews.com", "cbc.ca", "theglobeandmail.com", "bnnbloomberg.ca",
    "cnbc.com", "ft.com", "wsj.com", "bloomberg.com", "marketwatch.com", "barrons.com",
    "sec.gov", "sedarplus.ca", "bankofcanada.ca", "federalreserve.gov", "bls.gov", "statcan.gc.ca",
    "nasdaq.com", "tsx.com", "businesswire.com", "newswire.ca", "prnewswire.com", "globenewswire.com",
    # investor-relations sites of the starter universe
    "ir.tesla.com", "tesla.com", "nvidia.com", "investor.apple.com", "microsoft.com", "abc.xyz",
    "aboutamazon.com", "ir.aboutamazon.com", "jpmorganchase.com", "jnj.com", "pginvestor.com",
    "corporate.exxonmobil.com", "exxonmobil.com", "rbc.com", "td.com", "manulife.com", "enbridge.com",
    "cnrl.com", "cn.ca", "fortisinc.com", "corpo.couche-tard.com", "shopify.com", "csisoftware.com",
)

ESG_KEYWORDS = "controversy lawsuit environmental spill fine"


def _domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


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


def build_queries(ticker: str, name: str, contract: Mapping[str, Any]) -> list[str]:
    """2 or 3 searches: news, results/guidance, and controversies when ESG matters to the investor."""
    label = f"{name} {ticker.split('.')[0]}".strip()
    queries = [f"{label} news", f"{label} earnings results guidance"]
    esg = bool(contract.get("esg_exclusions")) or any(
        "esg" in str(p.get("id", "")).lower() or "esg" in str(p.get("text", "")).lower()
        for p in (contract.get("soft_preferences") or []) if isinstance(p, Mapping))
    if esg:
        queries.append(f"{label} {ESG_KEYWORDS}")
    return [q[:200] for q in queries]


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
    def _call(self, query: str) -> list[dict[str, Any]]:
        now = self._now()
        after = (now - timedelta(days=self.days)).strftime("%Y-%m-%dT00:00:00Z")
        before = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        response = self._search(
            webSearchId=WEB_SEARCH_ID,
            searchQuery=query[:200],
            maxResults=self.max_results,
            filters={"domainFilter": {"include": self.domains[:100]},
                     "publishedDateFilter": {"publishedAfter": after, "publishedBefore": before}},
        )
        return [dict(r) for r in (response.get("results") or []) if isinstance(r, Mapping)]

    def _record(self, registry: ExhibitRegistry, ticker: str, query: str,
                result: Mapping[str, Any], origin: str) -> Exhibit | None:
        url = str(result.get("url") or "").strip()
        title = str(result.get("title") or "").strip()
        if not url.startswith(("http://", "https://")) or not title:
            return None
        with self._lock:
            if url in self._seen or len(self._seen) >= self.max_exhibits:
                return None
            self._seen.add(url)
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
        snippet = " ".join(str(result.get("text") or "").split())[:SNIPPET_MAX_CHARS]
        retrieved = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        return registry.add(
            metric=WEB_METRIC,
            value={"title": title, "url": url, "source": _domain(url),
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
        found: list[Exhibit] = []
        for query in build_queries(ticker, name, contract):
            try:
                results = self._call(query)
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
            results = self._call(query)
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
