from pathlib import Path
ROOT=Path(__file__).parents[1]
def text(path): return (ROOT/path).read_text()
def test_models_are_account_scoped():
    m=text('app/models/tafsir.py')
    for name in ['TafsirBookmark','TafsirStudyNote','TafsirStudyCollection','TafsirStudyCollectionItem','TafsirStudyProgress']: assert f'class {name}' in m
    assert 'UniqueConstraint("user_id", "tafsir_entry_id")' in m
    assert "('not_started','in_progress','completed')" in m
def test_reader_is_publication_only_and_attributed():
    s=text('app/services/tafsir_reader.py')
    assert 'TafsirEntry.published.is_(True)' in s
    assert 'TafsirEdition.published.is_(True)' in s
    assert 'TafsirAuthor.published.is_(True)' in s
    assert 'KnowledgeCrossReference.published.is_(True)' in s
def test_private_writes_use_auth_and_csrf():
    r=text('app/api/routes/tafsir.py')
    for path in ["'/me/bookmarks'","'/me/notes'","'/me/collections'","'/me/progress'"]: assert path in r
    assert 'Depends(get_current_user)' in r and 'Depends(require_csrf)' in r
def test_migration_and_reader_ui_exist():
    migration=text('alembic/versions/20260725_0021_tafsir_study_tools.py')
    for table in ['tafsir_bookmarks','tafsir_study_notes','tafsir_study_collections','tafsir_study_collection_items','tafsir_study_progress']: assert table in migration
    ui=(ROOT.parent/'web/src/components/tafsir-reader.tsx').read_text()
    assert 'dir="rtl"' in ui and 'Cross-references' in ui and 'Copy citation' in ui
