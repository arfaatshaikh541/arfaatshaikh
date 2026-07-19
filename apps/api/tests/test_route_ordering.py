"""Milestone 10 hardening: a generic guard against the route-shadowing
bug class that hit this codebase twice by hand (ADR-0014's
`/leads/bulk/status` vs `/leads/{lead_id}/status`, and ADR-0016's
`/integrations/{id}/push/bulk` vs `/integrations/{id}/push/{lead_id}`) -
both were caught by manual review or a specific regression test for that
one instance, but nothing generic stopped a *third* recurrence. Starlette
resolves a request by walking its route table in registration order and
returning the first match; a parameterized segment (`{id}`) matches any
string, including one a later, more specific literal-segment sibling
route was meant to handle. If that literal route is registered *after*
the parameterized one, it is permanently unreachable.

This test introspects the real, fully-assembled FastAPI app (not a
hardcoded list of known-fixed instances) and flags any pair of routes,
sharing an HTTP method, whose path templates are identical except for
exactly one segment where one route has a literal and the other has a
parameter - unless the literal one is registered first, the way
Starlette's matching requires for it to ever be reachable.
"""

from fastapi.routing import APIRoute, _IncludedRouter


def _flatten_routes(routes) -> list[APIRoute]:
    """`app.routes` (this FastAPI version) holds `_IncludedRouter` wrapper
    objects for anything added via `include_router`, each wrapping the
    original `APIRouter` (whose own `.routes` are the real, ordered
    `APIRoute`s with the full mount-time path already applied) - not a
    flat list of `APIRoute`s directly. Recurses one level (this codebase
    never nests routers inside routers), preserving registration order
    both within a router and across routers, since that's the exact
    order Starlette's matcher walks."""
    flat: list[APIRoute] = []
    for route in routes:
        if isinstance(route, _IncludedRouter):
            flat.extend(_flatten_routes(route.original_router.routes))
        elif isinstance(route, APIRoute):
            flat.append(route)
    return flat


def _segments(path: str) -> list[str]:
    return [s for s in path.split("/") if s != ""]


def _is_param(segment: str) -> bool:
    return segment.startswith("{") and segment.endswith("}")


def _find_shadowed_routes(routes: list[APIRoute]) -> list[tuple[str, str]]:
    """Returns (parameterized_path, shadowed_literal_path) pairs where the
    parameterized route is registered before its literal-segment sibling,
    for every method they share. Only flags the exact single-segment-
    differs shape ADR-0014/ADR-0016's real bugs had - two routes with
    completely different literals in the same position (e.g. `/foo/bar`
    vs `/foo/baz`) are simply different endpoints, not a collision."""
    problems: list[tuple[str, str]] = []
    for i, r1 in enumerate(routes):
        segs1 = _segments(r1.path)
        r1_methods = r1.methods or set()
        for j, r2 in enumerate(routes):
            r2_methods = r2.methods or set()
            if i == j or not (r1_methods & r2_methods) or len(segs1) != len(_segments(r2.path)):
                continue
            segs2 = _segments(r2.path)
            differing_count = 0
            r1_has_the_param = False
            compatible = True
            for a, b in zip(segs1, segs2, strict=True):
                if a == b:
                    continue
                if _is_param(a) and _is_param(b):
                    continue
                if _is_param(a) and not _is_param(b):
                    differing_count += 1
                    r1_has_the_param = True
                elif _is_param(b) and not _is_param(a):
                    differing_count += 1
                    r1_has_the_param = False
                else:
                    compatible = False
                    break
            if compatible and differing_count == 1 and r1_has_the_param and i < j:
                problems.append((r1.path, r2.path))
    return problems


def test_no_literal_route_is_shadowed_by_an_earlier_parameterized_sibling():
    from app.main import app

    routes = _flatten_routes(app.routes)
    assert len(routes) > 50, (
        f"expected the full route table (~90+ routes as of Milestone 9), got {len(routes)} - "
        "did route flattening break against a FastAPI/Starlette internals change?"
    )

    problems = _find_shadowed_routes(routes)
    assert not problems, (
        "Route(s) permanently unreachable because a parameterized sibling is registered "
        "first - Starlette matches routes in registration order and a {param} segment "
        "matches any string, including a literal a later route was meant to handle. "
        "Register the literal-segment route(s) before the parameterized one (see "
        "docs/adr/0014 and docs/adr/0016 for two real instances of this exact bug):\n"
        + "\n".join(
            f"  {shadowed!r} is unreachable - {shadower!r} (registered first) matches "
            f"its concrete path too"
            for shadower, shadowed in problems
        )
    )
