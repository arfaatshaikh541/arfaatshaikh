"use client";
import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Button, Field, Notice, Surface } from "@world-of-islam/ui";
import { ApiError } from "@/lib/api";
import { getMessages } from "@/i18n/messages";
import { useAuth } from "./auth-provider";
export function LoginForm({locale}:{locale:Locale}) { const t=getMessages(locale), auth=useAuth(), router=useRouter(); const [error,setError]=useState(""); const [busy,setBusy]=useState(false);
async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();setError("");setBusy(true);const fd=new FormData(e.currentTarget);try{await auth.login(String(fd.get("email")),String(fd.get("password")));router.replace(`/${locale}/dashboard`);}catch(err){setError(err instanceof ApiError?err.message:"Sign-in failed.");}finally{setBusy(false)}}
return <Surface><form className="form-stack" onSubmit={submit} noValidate><Field name="email" type="email" autoComplete="email" required label={t.email}/><Field name="password" type="password" autoComplete="current-password" required label={t.password}/>{error?<Notice tone="danger">{error}</Notice>:null}<Button type="submit" disabled={busy}>{busy?t.loading:t.signIn}</Button><div className="form-links"><Link href={`/${locale}/forgot-password`}>{t.forgotPassword}</Link><Link href={`/${locale}/register`}>{t.register}</Link></div></form></Surface> }
