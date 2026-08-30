from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urljoin, urlsplit

import requests

MAX_RESPONSE_BYTES = 2_000_000
MAX_REDIRECTS = 4
ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
USER_AGENT = "VAHomeMath-GIS-ContentIntelligence/1.0 (+bounded research retrieval)"


class RetrievalError(RuntimeError):
    pass


@dataclass(frozen=True)
class RetrievalResult:
    requested_url: str
    resolved_url: str
    retrieved_at: datetime
    status_code: int
    content_type: str
    body: bytes
    truncated: bool
    headers: dict[str, str]


class ContentRetriever(Protocol):
    def retrieve(self, url: str) -> RetrievalResult: ...


def validate_public_http_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("URL must use HTTP(S) and include a hostname")
    if parts.username or parts.password:
        raise ValueError("URL credentials are not allowed")
    hostname = parts.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("local network targets are prohibited")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, parts.port or 443)}
    except socket.gaierror as error:
        raise ValueError("hostname could not be resolved") from error
    if not addresses:
        raise ValueError("hostname did not resolve")
    for raw_address in addresses:
        address = ipaddress.ip_address(raw_address)
        if not address.is_global:
            raise ValueError("private, local, link-local, and reserved targets are prohibited")
    return url


class DirectHTTPRetriever:
    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        max_bytes: int = MAX_RESPONSE_BYTES,
        timeout: tuple[float, float] = (5.0, 15.0),
    ) -> None:
        self.session = session or requests.Session()
        self.max_bytes = max_bytes
        self.timeout = timeout

    def retrieve(self, url: str) -> RetrievalResult:
        requested = validate_public_http_url(url)
        current = requested
        for redirect_count in range(MAX_REDIRECTS + 1):
            validate_public_http_url(current)
            try:
                response = self.session.get(
                    current,
                    headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
                    timeout=self.timeout,
                    allow_redirects=False,
                    stream=True,
                )
            except requests.RequestException as error:
                raise RetrievalError(f"HTTP retrieval failed: {type(error).__name__}") from error
            if response.is_redirect or response.is_permanent_redirect:
                if redirect_count >= MAX_REDIRECTS:
                    raise RetrievalError("redirect limit exceeded")
                location = response.headers.get("Location")
                if not location:
                    raise RetrievalError("redirect response omitted Location")
                current = urljoin(current, location)
                validate_public_http_url(current)
                continue
            media_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            if media_type not in ALLOWED_CONTENT_TYPES:
                raise RetrievalError("unsupported content type")
            body = bytearray()
            truncated = False
            for chunk in response.iter_content(chunk_size=65536):
                if len(body) + len(chunk) > self.max_bytes:
                    remaining = self.max_bytes - len(body)
                    body.extend(chunk[:remaining])
                    truncated = True
                    break
                body.extend(chunk)
            return RetrievalResult(
                requested_url=requested,
                resolved_url=current,
                retrieved_at=datetime.now(timezone.utc),
                status_code=response.status_code,
                content_type=response.headers.get("Content-Type", media_type),
                body=bytes(body),
                truncated=truncated,
                headers={
                    key: value
                    for key, value in response.headers.items()
                    if key.lower() in {"last-modified", "content-language"}
                },
            )
        raise RetrievalError("redirect limit exceeded")
