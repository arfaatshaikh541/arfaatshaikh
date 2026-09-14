'use client';
import {useEffect,useMemo,useState} from 'react';
import {apiFetch} from '@/lib/api';

type Item={entry:{id:string;reference:string;arabic_text:string};edition:{key:string;attribution:string};collection:{key:string;title:string};author:{name:string;arabic_name:string};translation:null|{text:string;key:string;translator:string;attribution:string};references:Array<{id:string;relationship_type:string;rationale:string}>};
export function TafsirReader({locale,surah,ayah}:{locale:string;surah:number;ayah:number}){
 const [items,setItems]=useState<Item[]>([]),[edition,setEdition]=useState(''),[translation,setTranslation]=useState(''),[status,setStatus]=useState('Loading reviewed commentary…');
 useEffect(()=>{const q=new URLSearchParams();if(edition)q.set('edition',edition);if(translation)q.set('translation',translation);apiFetch<Item[]>(`/tafsir/reader/${surah}/${ayah}?${q}`).then(d=>{setItems(d);setStatus(d.length?'':'No published commentary is available for this ayah.')}).catch(()=>setStatus('Reviewed Tafsir is currently unavailable.'));},[surah,ayah,edition,translation]);
 const editions=useMemo(()=>Array.from(new Set(items.map(x=>x.edition.key))),[items]);
 const copy=async(x:Item)=>{await navigator.clipboard.writeText(`${x.entry.arabic_text}\n\n${x.collection.title}, ${x.entry.reference}\n${location.href}#tafsir-${x.entry.id}`);setStatus('Citation copied.');};
 return <main className="reader-shell" aria-labelledby="tafsir-title"><header><p>Qur’an {surah}:{ayah}</p><h1 id="tafsir-title">{locale==='ar'?'التفسير':'Tafsir'}</h1><p>{locale==='ar'?'تُعرض أقوال العلماء منفصلة ومنسوبة إلى مصادرها.':'Scholarly commentaries remain separate and fully attributed.'}</p></header>
 <section aria-label="Reader controls"><label>Edition <select value={edition} onChange={e=>setEdition(e.target.value)}><option value="">All published editions</option>{editions.map(x=><option key={x}>{x}</option>)}</select></label><label>Translation key <input value={translation} onChange={e=>setTranslation(e.target.value)} placeholder="Optional published key"/></label></section>
 <p role="status" aria-live="polite">{status}</p>
 {items.map(x=><article id={`tafsir-${x.entry.id}`} key={x.entry.id} tabIndex={-1} className="tafsir-entry"><header><h2>{x.collection.title}</h2><p>{x.author.name} · {x.edition.key}</p><small>{x.edition.attribution}</small></header><div lang="ar" dir="rtl" className="arabic-text">{x.entry.arabic_text}</div>{x.translation&&<section><h3>{x.translation.translator}</h3><p>{x.translation.text}</p><small>{x.translation.attribution}</small></section>}{x.references.length>0&&<details><summary>Cross-references ({x.references.length})</summary><ul>{x.references.map(r=><li key={r.id}><strong>{r.relationship_type}</strong>: {r.rationale}</li>)}</ul></details>}<div className="reader-actions"><button onClick={()=>copy(x)}>Copy citation</button><button onClick={()=>apiFetch('/tafsir/me/bookmarks',{method:'POST',body:JSON.stringify({tafsir_entry_id:x.entry.id})}).then(()=>setStatus('Bookmark saved.')).catch(()=>setStatus('Sign in to save bookmarks.'))}>Bookmark</button></div></article>)}
 </main>;
}
