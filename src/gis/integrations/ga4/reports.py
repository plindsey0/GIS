from __future__ import annotations

from dataclasses import dataclass

from gis.integrations.ga4.config import GA4Dataset


@dataclass(frozen=True)
class ReportSpec:
    dataset: GA4Dataset
    dimensions: tuple[str, ...]
    metrics: tuple[str, ...]


REPORTS = {
    GA4Dataset.LANDING_PAGE: ReportSpec(
        GA4Dataset.LANDING_PAGE,
        (
            "date",
            "landingPage",
            "sessionDefaultChannelGroup",
            "sessionSource",
            "sessionMedium",
            "deviceCategory",
            "country",
        ),
        (
            "sessions",
            "activeUsers",
            "newUsers",
            "engagedSessions",
            "engagementRate",
            "averageSessionDuration",
            "eventCount",
            "keyEvents",
        ),
    ),
    GA4Dataset.ACQUISITION: ReportSpec(
        GA4Dataset.ACQUISITION,
        (
            "date",
            "sessionDefaultChannelGroup",
            "sessionSource",
            "sessionMedium",
            "sessionCampaignName",
            "deviceCategory",
            "country",
        ),
        (
            "sessions",
            "activeUsers",
            "newUsers",
            "engagedSessions",
            "engagementRate",
            "eventCount",
            "keyEvents",
        ),
    ),
    GA4Dataset.EVENTS: ReportSpec(
        GA4Dataset.EVENTS,
        (
            "date",
            "eventName",
            "landingPage",
            "pagePath",
            "sessionDefaultChannelGroup",
            "deviceCategory",
            "country",
        ),
        ("eventCount", "totalUsers", "eventCountPerActiveUser", "keyEvents"),
    ),
}
