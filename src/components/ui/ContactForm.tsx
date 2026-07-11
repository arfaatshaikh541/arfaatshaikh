"use client";

import { useState, type FormEvent } from "react";
import { services } from "@/data/services";
import { Button } from "./Button";

type Status = "idle" | "submitting" | "success" | "error";

export default function ContactForm() {
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus("submitting");
    setErrorMessage("");

    const form = e.currentTarget;
    const data = Object.fromEntries(new FormData(form).entries());

    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error ?? "Something went wrong. Please try again.");
      }

      setStatus("success");
      form.reset();
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    }
  }

  if (status === "success") {
    return (
      <div role="status" className="gk-card flex flex-col gap-2 p-8">
        <p className="font-display text-xl uppercase tracking-wide text-orange-bright">Request Received</p>
        <p className="text-sm text-muted">
          Thank you — your project request has been received. GRIDKEEP will respond directly to review next steps.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="gk-card flex flex-col gap-5 p-6 md:p-8" noValidate>
      <p className="gk-eyebrow">Tell Us About Your Project</p>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <Field label="Name" name="name" required autoComplete="name" />
        <Field label="Work Email" name="email" type="email" required autoComplete="email" />
      </div>

      <Field label="Company" name="company" autoComplete="organization" />

      <div className="flex flex-col gap-2">
        <label htmlFor="service" className="font-mono text-[11px] uppercase tracking-[0.1em] text-muted">
          Select a Service
        </label>
        <select
          id="service"
          name="service"
          defaultValue=""
          className="border border-line bg-black-graphite px-4 py-3 text-sm text-warmwhite focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-bright"
        >
          <option value="" disabled>
            Choose a service
          </option>
          {services.map((s) => (
            <option key={s.slug} value={s.title}>
              {s.title}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor="message" className="font-mono text-[11px] uppercase tracking-[0.1em] text-muted">
          Project Description
        </label>
        <textarea
          id="message"
          name="message"
          required
          rows={5}
          className="resize-none border border-line bg-black-graphite px-4 py-3 text-sm text-warmwhite focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-bright"
        />
      </div>

      {status === "error" && (
        <p role="alert" className="text-xs text-orange-hot">
          {errorMessage}
        </p>
      )}

      <Button type="submit" disabled={status === "submitting"} className="justify-center">
        {status === "submitting" ? "Submitting…" : "Submit Request →"}
      </Button>
    </form>
  );
}

function Field({
  label,
  name,
  type = "text",
  required,
  autoComplete,
}: {
  label: string;
  name: string;
  type?: string;
  required?: boolean;
  autoComplete?: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={name} className="font-mono text-[11px] uppercase tracking-[0.1em] text-muted">
        {label}
        {required && <span className="text-orange-primary"> *</span>}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        required={required}
        autoComplete={autoComplete}
        className="border border-line bg-black-graphite px-4 py-3 text-sm text-warmwhite focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-bright"
      />
    </div>
  );
}
