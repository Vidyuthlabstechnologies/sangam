"""In-process Prometheus metrics. No collector process is required.

Labels are the route template (or "unmatched"), the method, and the status.
Raw paths are not used: they can contain phone numbers and document ids.
Bodies, prompts, tokens, and headers are never recorded.
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "sangam_http_requests_total",
    "HTTP responses by method, route template, and status.",
    ("method", "path", "status"),
)
HTTP_LATENCY = Histogram(
    "sangam_http_request_duration_seconds",
    "HTTP request latency by method and route template.",
    ("method", "path"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)


def route_label(request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if not path:
        return "unmatched"
    return str(path)
