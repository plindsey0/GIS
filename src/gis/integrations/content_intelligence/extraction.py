from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "but",
    "can",
    "for",
    "from",
    "has",
    "have",
    "how",
    "into",
    "its",
    "more",
    "not",
    "our",
    "that",
    "the",
    "their",
    "this",
    "through",
    "use",
    "what",
    "when",
    "where",
    "which",
    "with",
    "you",
    "your",
}
SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer"}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_url(value: str) -> tuple[str, str, str]:
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("content URL must be absolute HTTP(S)")
    hostname = parts.hostname.encode("idna").decode("ascii").lower().removeprefix("www.")
    port = f":{parts.port}" if parts.port and parts.port not in {80, 443} else ""
    normalized = urlunsplit(
        (parts.scheme.lower(), f"{hostname}{port}", parts.path or "/", parts.query, "")
    )
    return normalized, hostname, parts.path or "/"


@dataclass
class ExtractedPage:
    title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    language: str | None = None
    robots: list[str] = field(default_factory=list)
    visible_text: str = ""
    paragraph_count: int = 0
    tag_counts: Counter[str] = field(default_factory=Counter)
    headings: list[tuple[int, str]] = field(default_factory=list)
    schema_types: Counter[str] = field(default_factory=Counter)
    links: list[dict[str, object]] = field(default_factory=list)
    components: list[dict[str, object]] = field(default_factory=list)
    terms: Counter[str] = field(default_factory=Counter)
    publication_dates: list[dict[str, str]] = field(default_factory=list)
    modified_dates: list[dict[str, str]] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return len(re.findall(r"\b[\w'-]+\b", self.visible_text, re.UNICODE))


class _PageParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.page = ExtractedPage()
        self.stack: list[str] = []
        self.text_parts: list[str] = []
        self.capture: str | None = None
        self.capture_parts: list[str] = []
        self.current_link: dict[str, object] | None = None
        self.json_ld = False
        self.json_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs = {key.lower(): value or "" for key, value in attrs_list}
        self.stack.append(tag)
        self.page.tag_counts[tag] += 1
        if tag == "html" and attrs.get("lang"):
            self.page.language = attrs["lang"][:32]
        if tag == "meta":
            name = attrs.get("name", "").lower()
            prop = attrs.get("property", "").lower()
            if name == "description":
                self.page.meta_description = attrs.get("content")
            if name in {"robots", "googlebot"}:
                self.page.robots.extend(
                    part.strip().lower()
                    for part in attrs.get("content", "").split(",")
                    if part.strip()
                )
            date_value = attrs.get("content")
            if date_value and ("published" in prop or "published" in name):
                self.page.publication_dates.append(
                    {"value": date_value, "source": f"meta:{prop or name}"}
                )
            if date_value and ("modified" in prop or "modified" in name):
                self.page.modified_dates.append(
                    {"value": date_value, "source": f"meta:{prop or name}"}
                )
        if tag == "link" and "canonical" in attrs.get("rel", "").lower().split():
            self.page.canonical_url = urljoin(self.base_url, attrs.get("href", ""))
        if tag == "title" or re.fullmatch(r"h[1-6]", tag):
            self.capture, self.capture_parts = tag, []
        if tag == "p":
            self.page.paragraph_count += 1
        if tag == "a" and attrs.get("href"):
            rel = sorted(set(attrs.get("rel", "").lower().split()))
            self.current_link = {
                "url": urljoin(self.base_url, attrs["href"]),
                "rel": rel,
                "anchor": "",
            }
        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self.json_ld, self.json_parts = True, []
        if tag == "time" and attrs.get("datetime"):
            target = (
                self.page.modified_dates
                if "mod" in attrs.get("class", "").lower()
                else self.page.publication_dates
            )
            target.append({"value": attrs["datetime"], "source": "time:datetime"})

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.capture == tag:
            value = normalize_text(" ".join(self.capture_parts))
            if tag == "title":
                self.page.title = value or None
            elif value:
                self.page.headings.append((int(tag[1]), value))
            self.capture = None
        if tag == "a" and self.current_link:
            self.page.links.append(self.current_link)
            self.current_link = None
        if tag == "script" and self.json_ld:
            self._extract_json_ld("".join(self.json_parts))
            self.json_ld = False
        if self.stack:
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index] == tag:
                    del self.stack[index:]
                    break

    def handle_data(self, data: str) -> None:
        if self.json_ld:
            self.json_parts.append(data)
            return
        clean = normalize_text(data)
        if not clean:
            return
        if self.capture:
            self.capture_parts.append(clean)
        if self.current_link:
            self.current_link["anchor"] = normalize_text(
                f"{self.current_link.get('anchor', '')} {clean}"
            )
        if not any(tag in SKIP_TAGS for tag in self.stack):
            self.text_parts.append(clean)

    def _extract_json_ld(self, raw: str) -> None:
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return
        pending = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, list):
                pending.extend(item)
            elif isinstance(item, dict):
                raw_type = item.get("@type")
                for schema_type in raw_type if isinstance(raw_type, list) else [raw_type]:
                    if isinstance(schema_type, str) and schema_type:
                        self.page.schema_types[schema_type] += 1
                graph = item.get("@graph")
                if isinstance(graph, (dict, list)):
                    pending.append(graph)


def extract_page(html: bytes, base_url: str, encoding: str = "utf-8") -> ExtractedPage:
    parser = _PageParser(base_url)
    parser.feed(html.decode(encoding, errors="replace"))
    page = parser.page
    page.visible_text = normalize_text(" ".join(parser.text_parts))
    source_domain = normalize_url(base_url)[1]
    normalized_links: list[dict[str, object]] = []
    for link in page.links:
        try:
            normalized, domain, _ = normalize_url(str(link["url"]))
        except ValueError:
            continue
        normalized_links.append(
            {
                "url": normalized,
                "domain": domain,
                "class": "INTERNAL" if domain == source_domain else "EXTERNAL",
                "anchor": link.get("anchor") or None,
                "rel": link["rel"],
            }
        )
    page.links = normalized_links
    page.components = detect_components(page)
    page.terms = extract_terms(page)
    return page


def detect_components(page: ExtractedPage) -> list[dict[str, object]]:
    heading_text = " ".join(text.casefold() for _, text in page.headings)
    text = page.visible_text.casefold()
    measured = {
        "TABLE": page.tag_counts["table"],
        "FORM": page.tag_counts["form"],
        "VIDEO": page.tag_counts["video"] + page.tag_counts["iframe"],
        "BREADCRUMB": page.schema_types["BreadcrumbList"],
    }
    result = [
        {
            "type": kind,
            "count": count,
            "method": "DOM_TAG_OR_SCHEMA",
            "confidence": "1.0",
            "semantics": "MEASURED",
        }
        for kind, count in measured.items()
        if count
    ]
    heuristics = {
        "FAQ": ("faq" in heading_text or "frequently asked" in heading_text),
        "CALCULATOR_OR_TOOL": bool(
            re.search(r"\b(calculator|calculate|estimator|interactive tool)\b", heading_text)
        ),
        "REFERENCES_SECTION": bool(re.search(r"\b(references|sources|citations)\b", heading_text)),
        "AUTHOR_BYLINE": bool(re.search(r"\b(by|author)\s+[A-Z]", page.visible_text[:1000])),
        "CTA": bool(re.search(r"\b(get started|apply now|learn more|contact us)\b", text)),
    }
    result.extend(
        {
            "type": kind,
            "count": 1,
            "method": "LEXICAL_HEURISTIC_V1",
            "confidence": "0.7",
            "semantics": "HEURISTIC",
        }
        for kind, present in heuristics.items()
        if present
    )
    return result


def extract_terms(page: ExtractedPage) -> Counter[str]:
    counts: Counter[str] = Counter()
    for _, heading in page.headings:
        tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", heading.casefold())
            if len(token) > 2 and token not in STOPWORDS
        ]
        for size in (1, 2, 3):
            counts.update(
                " ".join(tokens[index : index + size]) for index in range(len(tokens) - size + 1)
            )
    return counts
