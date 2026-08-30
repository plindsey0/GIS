from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

SIGNATURE_REGISTRY_VERSION = "2026-08-30.1"


@dataclass(frozen=True)
class TechnologyDefinition:
    slug: str
    name: str
    vendor: str | None
    category: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class TechnologySignature:
    key: str
    technology_slug: str
    target: str
    pattern: str
    match_type: str
    confidence: Decimal
    semantic_class: str
    scope: str = "PAGE"
    active: bool = True


TECHNOLOGIES = (
    TechnologyDefinition("wordpress", "WordPress", "Automattic", "CMS", ("WordPress CMS",)),
    TechnologyDefinition("nextjs", "Next.js", "Vercel", "WEB_FRAMEWORK", ("NextJS", "Next JS")),
    TechnologyDefinition("react", "React", "Meta", "JAVASCRIPT_FRAMEWORK", ("React.js", "ReactJS")),
    TechnologyDefinition(
        "google_analytics", "Google Analytics", "Google", "ANALYTICS", ("Google Analytics 4", "GA4")
    ),
    TechnologyDefinition(
        "google_tag_manager", "Google Tag Manager", "Google", "TAG_MANAGER", ("GTM",)
    ),
    TechnologyDefinition("cloudflare", "Cloudflare", "Cloudflare", "CDN", ("Cloudflare CDN",)),
    TechnologyDefinition("vercel", "Vercel", "Vercel", "HOSTING", ()),
    TechnologyDefinition("nginx", "NGINX", "F5", "REVERSE_PROXY", ("Nginx",)),
    TechnologyDefinition("hubspot", "HubSpot", "HubSpot", "MARKETING_AUTOMATION", ()),
    TechnologyDefinition("hotjar", "Hotjar", "Contentsquare", "SESSION_REPLAY", ()),
    TechnologyDefinition("optimizely", "Optimizely", "Optimizely", "AB_TESTING", ()),
    TechnologyDefinition("recaptcha", "Google reCAPTCHA", "Google", "CAPTCHA", ("reCAPTCHA",)),
)


SIGNATURES = (
    TechnologySignature(
        "wordpress.asset.v1",
        "wordpress",
        "HTML",
        "/wp-content/",
        "CONTAINS",
        Decimal("0.95"),
        "HEURISTIC",
        "SITE",
    ),
    TechnologySignature(
        "wordpress.generator.v1",
        "wordpress",
        "META_GENERATOR",
        "wordpress",
        "CONTAINS",
        Decimal("0.99"),
        "HEURISTIC",
        "SITE",
    ),
    TechnologySignature(
        "nextjs.asset.v1",
        "nextjs",
        "HTML",
        "/_next/",
        "CONTAINS",
        Decimal("0.95"),
        "HEURISTIC",
        "SITE",
    ),
    TechnologySignature(
        "react.root.v1",
        "react",
        "HTML",
        "data-reactroot",
        "CONTAINS",
        Decimal("0.75"),
        "HEURISTIC",
        "PAGE",
    ),
    TechnologySignature(
        "ga.script.v1",
        "google_analytics",
        "HTML",
        "google-analytics.com/analytics.js",
        "CONTAINS",
        Decimal("0.99"),
        "HEURISTIC",
        "PAGE",
    ),
    TechnologySignature(
        "ga.gtag.v1",
        "google_analytics",
        "HTML",
        "googletagmanager.com/gtag/js",
        "CONTAINS",
        Decimal("0.99"),
        "HEURISTIC",
        "PAGE",
    ),
    TechnologySignature(
        "gtm.script.v1",
        "google_tag_manager",
        "HTML",
        "googletagmanager.com/gtm.js",
        "CONTAINS",
        Decimal("0.99"),
        "HEURISTIC",
        "PAGE",
    ),
    TechnologySignature(
        "cloudflare.server.v1",
        "cloudflare",
        "HEADER_SERVER",
        "cloudflare",
        "CONTAINS",
        Decimal("1.0"),
        "MEASURED",
        "SITE",
    ),
    TechnologySignature(
        "cloudflare.ray.v1",
        "cloudflare",
        "HEADER_CF_RAY",
        "",
        "PRESENT",
        Decimal("1.0"),
        "MEASURED",
        "SITE",
    ),
    TechnologySignature(
        "vercel.header.v1",
        "vercel",
        "HEADER_X_VERCEL_ID",
        "",
        "PRESENT",
        Decimal("1.0"),
        "MEASURED",
        "SITE",
    ),
    TechnologySignature(
        "nginx.server.v1",
        "nginx",
        "HEADER_SERVER",
        "nginx",
        "CONTAINS",
        Decimal("1.0"),
        "MEASURED",
        "SITE",
    ),
    TechnologySignature(
        "hubspot.script.v1",
        "hubspot",
        "HTML",
        "js.hs-scripts.com",
        "CONTAINS",
        Decimal("0.99"),
        "HEURISTIC",
    ),
    TechnologySignature(
        "hotjar.script.v1",
        "hotjar",
        "HTML",
        "static.hotjar.com",
        "CONTAINS",
        Decimal("0.99"),
        "HEURISTIC",
    ),
    TechnologySignature(
        "optimizely.script.v1",
        "optimizely",
        "HTML",
        "cdn.optimizely.com",
        "CONTAINS",
        Decimal("0.99"),
        "HEURISTIC",
    ),
    TechnologySignature(
        "recaptcha.script.v1",
        "recaptcha",
        "HTML",
        "google.com/recaptcha/",
        "CONTAINS",
        Decimal("0.99"),
        "HEURISTIC",
    ),
)
