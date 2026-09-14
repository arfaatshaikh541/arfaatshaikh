"use client";
import type { Locale } from "@world-of-islam/shared-types";
import { FormEvent, useState } from "react";
import { Button, Field, Notice, Surface } from "@world-of-islam/ui";
import { apiFetch, ApiError } from "@/lib/api";
import { getMessages } from "@/i18n/messages";
export function ForgotPasswordForm({locale}:{locale:Locale}){const t=getMessages(locale);const [message,setMessage]=useState("");const [error,setError]=useState("");async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();setError("");try{const fd=new FormData(e.currentTarget);const r=await apiFetch<{message:string}>("/auth/password-reset/request",{method:"POST",body:JSON.stringify({email:fd.get("email")})});setMessage(r.message);}catch(err){setError(err instanceof ApiError?err.message:"Request failed.")}}return <Surface><form className="form-stack" onSubmit={submit}><Field name="email" type="email" required autoComplete="email" label={t.email}/>{message?<Notice tone="success">{message}</Notice>:null}{error?<Notice tone="danger">{error}</Notice>:null}<Button type="submit">Send reset instructions</Button></form></Surface>}
