"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

type Bookmark={id:string;ayah_id:string;canonical_reference:string;note:string|null};

export function QuranBookmarks({locale}:{locale:"en"|"ar"}){
  const ar=locale==="ar"; const [items,setItems]=useState<Bookmark[]>([]); const [message,setMessage]=useState(ar?"جارٍ التحميل…":"Loading bookmarks…");
  useEffect(()=>{apiFetch<Bookmark[]>("/quran/me/bookmarks").then(x=>{setItems(x);setMessage("");}).catch(()=>setMessage(ar?"سجّل الدخول لعرض العلامات.":"Sign in to view bookmarks."));},[ar]);
  async function remove(id:string){try{await apiFetch(`/quran/me/bookmarks/${id}`,{method:"DELETE"});setItems(x=>x.filter(i=>i.id!==id));}catch{setMessage(ar?"تعذر حذف العلامة.":"Bookmark could not be removed.");}}
  return <main className="quran-reader-page"><header className="reader-toolbar"><Link href={`/${locale}/quran`}>{ar?"فهرس السور":"Surah index"}</Link><h1>{ar?"علاماتي":"My bookmarks"}</h1></header>{message&&<div role="status" className="trust-banner">{message}</div>}<ol className="ayah-list">{items.map(item=>{const [surah,ayah]=item.canonical_reference.split(":");return <li key={item.id} className="ayah-card"><Link href={`/${locale}/quran/${surah}#ayah-${ayah}`}>{item.canonical_reference}</Link>{item.note&&<p>{item.note}</p>}<button onClick={()=>remove(item.id)}>{ar?"حذف":"Remove"}</button></li>})}</ol></main>;
}
