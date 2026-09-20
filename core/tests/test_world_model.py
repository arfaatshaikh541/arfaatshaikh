from __future__ import annotations

import json

from aura_core.memory import WorldModelStore


def make_store(tmp_path) -> WorldModelStore:
    return WorldModelStore(f"sqlite:///{tmp_path}/world.db")


def test_create_and_fetch_entity(tmp_path):
    store = make_store(tmp_path)
    entity = store.upsert_entity(
        entity_type="company", name="Gridkeep", source="unit-test",
        attributes={"industry": "property management"},
    )
    fetched = store.get_entity(entity.id)
    assert fetched is not None
    assert fetched.name == "Gridkeep"
    assert json.loads(fetched.attributes_json)["industry"] == "property management"


def test_upsert_updates_existing_entity_in_place(tmp_path):
    store = make_store(tmp_path)
    entity = store.upsert_entity(entity_type="company", name="Gridkeep", source="unit-test")

    store.upsert_entity(
        entity_type="company", name="Gridkeep Ltd", source="unit-test-2",
        attributes={"renamed": True}, entity_id=entity.id,
    )

    fetched = store.get_entity(entity.id)
    assert fetched.name == "Gridkeep Ltd"
    assert json.loads(fetched.attributes_json)["renamed"] is True
    assert store.find_entities(entity_type="company") == [fetched] or len(store.find_entities(entity_type="company")) == 1


def test_upsert_with_new_id_creates_with_that_exact_id(tmp_path):
    store = make_store(tmp_path)
    entity = store.upsert_entity(entity_type="person", name="Ahmed", source="unit-test", entity_id="ahmed-1")
    assert entity.id == "ahmed-1"
    assert store.get_entity("ahmed-1") is not None


def test_find_entities_by_type_and_name(tmp_path):
    store = make_store(tmp_path)
    store.upsert_entity(entity_type="person", name="Ahmed Khan", source="unit-test")
    store.upsert_entity(entity_type="person", name="Sara Ali", source="unit-test")
    store.upsert_entity(entity_type="company", name="Gridkeep", source="unit-test")

    people = store.find_entities(entity_type="person")
    assert len(people) == 2

    ahmed_matches = store.find_entities(name_contains="Ahmed")
    assert len(ahmed_matches) == 1
    assert ahmed_matches[0].name == "Ahmed Khan"


def test_relationships_link_two_entities_and_are_queryable_both_directions(tmp_path):
    store = make_store(tmp_path)
    ahmed = store.upsert_entity(entity_type="person", name="Ahmed", source="unit-test")
    gridkeep = store.upsert_entity(entity_type="company", name="Gridkeep", source="unit-test")

    store.link(subject_id=ahmed.id, predicate="works_at", object_id=gridkeep.id, source="unit-test")

    outgoing = store.relationships_from(ahmed.id, predicate="works_at")
    assert len(outgoing) == 1
    assert outgoing[0].object_id == gridkeep.id

    incoming = store.relationships_to(gridkeep.id, predicate="works_at")
    assert len(incoming) == 1
    assert incoming[0].subject_id == ahmed.id

    assert store.relationships_from(ahmed.id, predicate="owns") == []
