"use client";

import Link from "next/link";
import { NOT_PUBLIC } from "@/lib/copy";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Collection = { collection_key: string; arabic_title: string; display_title: string; compiler_name: string };
type Book = { book_number: number; arabic_title: string; display_title: string };

export function HadithBrowser({ locale, collection }: { locale: "en" | "ar"; collection?: string }) {
  const ar = locale === "ar";
  const [collections, setCollections] = useState<Collection[] | null>(null);
  const [books, setBooks] = useState<Book[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (collection) apiFetch<Book[]>(`/hadith/collections/${encodeURIComponent(collection)}/books`).then(setBooks).catch(() => setError(true));
    else apiFetch<Collection[]>("/hadith/collections").then(setCollections).catch(() => setError(true));
  }, [collection]);

  if (error) return <p role="alert">{ar ? "تعذّر تحميل القائمة." : "The list could not be loaded."}</p>;
  if (collection) {
    if (!books) return <p role="status">{ar ? "جارٍ التحميل…" : "Loading…"}</p>;
    return (
      <ol className="surah-list">
        {books.map((b) => (
          <li key={b.book_number}>
            <Link href={`/${locale}/hadith/${collection}/${b.book_number}/1`}>
              <span>{b.book_number}</span>
              <strong lang="ar" dir="rtl">{b.arabic_title}</strong>
              <em>{b.display_title}</em>
            </Link>
          </li>
        ))}
      </ol>
    );
  }
  if (!collections) return <p role="status">{ar ? "جارٍ التحميل…" : "Loading…"}</p>;
  if (collections.length === 0) return <p role="status">{NOT_PUBLIC[ar ? "ar" : "en"]}</p>;
  return (
    <ol className="surah-list">
      {collections.map((c) => (
        <li key={c.collection_key}>
          <Link href={`/${locale}/hadith/${c.collection_key}`}>
            <span>·</span>
            <strong lang="ar" dir="rtl">{c.arabic_title}</strong>
            <em>{c.display_title}</em>
            <small>{c.compiler_name}</small>
          </Link>
        </li>
      ))}
    </ol>
  );
}
