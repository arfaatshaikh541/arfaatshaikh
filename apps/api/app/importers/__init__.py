"""Source adapters: one small class per legitimate source, a shared runner, and a registry.

An adapter knows how to fetch exactly one verified source and map it to the platform's data contract without inventing
anything. The runner validates (preview), applies all-or-nothing, and records the source version, retrieval time and
checksum on the import so an administrator can see and re-run it safely.
"""
from app.importers.base import AdapterResult, FetchResult, SourceAdapter  # noqa: F401
from app.importers.registry import ADAPTERS, get_adapter  # noqa: F401
