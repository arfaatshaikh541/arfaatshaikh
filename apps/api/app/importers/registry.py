from app.importers.base import SourceAdapter
from app.importers.geoalgeria import GeoAlgeriaMosques
from app.importers.hadith_grades import HadithApiGrades
from app.importers.osm_overpass import OsmOverpassMosques

ADAPTERS: dict[str, SourceAdapter] = {a.id: a for a in (GeoAlgeriaMosques(), HadithApiGrades(), OsmOverpassMosques())}


def get_adapter(adapter_id: str) -> SourceAdapter:
    try:
        return ADAPTERS[adapter_id]
    except KeyError as exc:
        raise KeyError(f"unknown importer {adapter_id!r}; known: {', '.join(sorted(ADAPTERS))}") from exc
