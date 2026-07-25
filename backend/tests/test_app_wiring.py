"""Guards against router-registration mistakes in app.main.

A router included twice silently double-mounts every one of its routes.
FastAPI does not complain; the duplicates just shadow each other and
bloat the OpenAPI schema.
"""
from app.main import app


def test_no_duplicate_routes():
    seen: dict[tuple, int] = {}
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = tuple(sorted(getattr(route, "methods", None) or []))
        key = (path, methods)
        seen[key] = seen.get(key, 0) + 1

    duplicates = {k: v for k, v in seen.items() if v > 1}
    assert not duplicates, f"Duplicate routes registered: {duplicates}"


def test_health_route_registered():
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/health" in paths
