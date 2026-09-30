"""Publish (or hide again) Qur'an translations and tafsirs that were imported but left unpublished.

Translations and tafsirs whose copyright status is not confirmed are stored *staged*: present in the
database with their provenance, but hidden from readers and search. Run this only after you have
confirmed that you may publish the work (licence, written permission, or the publisher's terms).

    uv run python scripts/publish_staged.py --list
    uv run python scripts/publish_staged.py --translations eng-abdullahyusufal --i-have-permission
    uv run python scripts/publish_staged.py --tafsir ar-tafsir-as-saadi --i-have-permission
    uv run python scripts/publish_staged.py --all-translations --i-have-permission
    uv run python scripts/publish_staged.py --translations eng-abdullahyusufal --unpublish

The flag --i-have-permission is required to publish: it is your statement that the rights are cleared.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, select, update

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.models.quran import QuranAyahTranslation, QuranTranslationEdition  # noqa: E402
from app.models.tafsir import TafsirAuthor, TafsirCollection, TafsirEdition, TafsirEntry  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="show what is staged and what is published")
    ap.add_argument("--translations", nargs="*", default=[], help="translation keys, e.g. eng-abdullahyusufal")
    ap.add_argument("--tafsir", nargs="*", default=[], help="tafsir edition keys, e.g. ar-tafsir-as-saadi")
    ap.add_argument("--all-translations", action="store_true")
    ap.add_argument("--all-tafsir", action="store_true")
    ap.add_argument("--unpublish", action="store_true", help="hide the chosen items again")
    ap.add_argument("--i-have-permission", action="store_true", help="confirm the rights to publish are cleared")
    args = ap.parse_args()
    flag = not args.unpublish

    db = Database(get_settings())
    async with db.session_factory() as session:
        if args.list:
            for label, model, key in (("Qur'an translations", QuranTranslationEdition, QuranTranslationEdition.translation_key),
                                      ("Tafsir editions", TafsirEdition, TafsirEdition.edition_key)):
                rows = (await session.execute(select(model.published, func.count()).group_by(model.published))).all()
                print(label, {("published" if p else "staged"): n for p, n in rows})
            return

        chosen_t = args.translations or ([] if not args.all_translations else None)
        chosen_f = args.tafsir or ([] if not args.all_tafsir else None)
        if chosen_t == [] and chosen_f == []:
            raise SystemExit("Nothing selected. Use --list, --translations, --tafsir, --all-translations or --all-tafsir.")
        if flag and not args.i_have_permission:
            raise SystemExit("Publishing needs --i-have-permission: confirm that you may publish these works.")

        if chosen_t != []:
            q = select(QuranTranslationEdition.id, QuranTranslationEdition.translation_key)
            if chosen_t is not None:
                q = q.where(QuranTranslationEdition.translation_key.in_(chosen_t))
            found = (await session.execute(q)).all()
            ids = [i for i, _ in found]
            missing = set(chosen_t or []) - {k for _, k in found}
            if missing:
                print("Not found:", ", ".join(sorted(missing)))
            if ids:
                await session.execute(update(QuranTranslationEdition).where(QuranTranslationEdition.id.in_(ids)).values(published=flag))
                await session.execute(update(QuranAyahTranslation).where(QuranAyahTranslation.translation_edition_id.in_(ids)).values(published=flag))
            print(f"{'Published' if flag else 'Hidden'} {len(ids)} translation editions")

        if chosen_f != []:
            q = select(TafsirEdition.id, TafsirEdition.collection_id, TafsirEdition.edition_key)
            if chosen_f is not None:
                q = q.where(TafsirEdition.edition_key.in_(chosen_f))
            found = (await session.execute(q)).all()
            eids = [i for i, _, _ in found]
            cids = [c for _, c, _ in found]
            missing = set(chosen_f or []) - {k for _, _, k in found}
            if missing:
                print("Not found:", ", ".join(sorted(missing)))
            if eids:
                await session.execute(update(TafsirEdition).where(TafsirEdition.id.in_(eids)).values(published=flag))
                await session.execute(update(TafsirEntry).where(TafsirEntry.edition_id.in_(eids)).values(published=flag))
                await session.execute(update(TafsirCollection).where(TafsirCollection.id.in_(cids)).values(published=flag))
                author_ids = (await session.scalars(select(TafsirCollection.author_id).where(TafsirCollection.id.in_(cids)))).all()
                if flag:
                    await session.execute(update(TafsirAuthor).where(TafsirAuthor.id.in_(set(author_ids))).values(published=True))
            print(f"{'Published' if flag else 'Hidden'} {len(eids)} tafsir editions")
        await session.commit()
    await db.dispose()
    print("Note: the licence record in the source registry still says 'rights not cleared'; update it in the admin area to match your permission.")


if __name__ == "__main__":
    asyncio.run(main())
