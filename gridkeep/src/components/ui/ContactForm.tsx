"use client";

import { useId, useState, type FormEvent } from "react";

const SERVICES = [
  "AI & AI Agents",
  "Business Automation",
  "Custom Software",
  "Cybersecurity",
  "Cloud & DevOps",
  "Business Systems",
  "Web Experiences",
  "Not sure yet",
];

const BUDGETS = ["Under $10k", "$10k – $50k", "$50k – $150k", "$150k+", "Prefer to discuss"];

const CONTACT_METHODS = ["Email", "Phone", "Either"];

type Status = "idle" | "submitting" | "success" | "error";

export default function ContactForm() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const formId = useId();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const form = event.currentTarget;
    const data = new FormData(form);

    if (!data.get("privacy")) {
      setError("Please confirm you agree to the privacy policy before submitting.");
      return;
    }

    setStatus("submitting");
    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.fromEntries(data.entries())),
      });
      if (!res.ok) throw new Error("Request failed");
      setStatus("success");
      form.reset();
    } catch {
      setStatus("error");
      setError("Something interrupted the transmission. Please try again or email hello@gridkeep.com directly.");
    }
  }

  if (status === "success") {
    return (
      <div role="status" className="gk-panel border border-gk-orange/50 p-8 text-center">
        <p className="gk-eyebrow">Transmission Received</p>
        <p className="font-display mt-3 text-2xl text-gk-white">Project intake logged.</p>
        <p className="mt-3 text-sm text-gk-grey">
          We&apos;ll respond from hello@gridkeep.com within two business days.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-5 sm:grid-cols-2" noValidate>
      <div className="flex flex-col gap-2">
        <label htmlFor={`${formId}-name`} className="font-mono-tech text-xs uppercase tracking-[0.12em] text-gk-grey">
          Name <span className="text-gk-orange">*</span>
        </label>
        <input
          id={`${formId}-name`}
          name="name"
          type="text"
          required
          autoComplete="name"
          className="border border-gk-steel bg-gk-black px-4 py-3 text-sm text-gk-white outline-none focus:border-gk-orange"
        />
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor={`${formId}-email`} className="font-mono-tech text-xs uppercase tracking-[0.12em] text-gk-grey">
          Work Email <span className="text-gk-orange">*</span>
        </label>
        <input
          id={`${formId}-email`}
          name="email"
          type="email"
          required
          autoComplete="email"
          className="border border-gk-steel bg-gk-black px-4 py-3 text-sm text-gk-white outline-none focus:border-gk-orange"
        />
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor={`${formId}-company`} className="font-mono-tech text-xs uppercase tracking-[0.12em] text-gk-grey">
          Company
        </label>
        <input
          id={`${formId}-company`}
          name="company"
          type="text"
          autoComplete="organization"
          className="border border-gk-steel bg-gk-black px-4 py-3 text-sm text-gk-white outline-none focus:border-gk-orange"
        />
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor={`${formId}-phone`} className="font-mono-tech text-xs uppercase tracking-[0.12em] text-gk-grey">
          Phone
        </label>
        <input
          id={`${formId}-phone`}
          name="phone"
          type="tel"
          autoComplete="tel"
          className="border border-gk-steel bg-gk-black px-4 py-3 text-sm text-gk-white outline-none focus:border-gk-orange"
        />
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor={`${formId}-service`} className="font-mono-tech text-xs uppercase tracking-[0.12em] text-gk-grey">
          Service <span className="text-gk-orange">*</span>
        </label>
        <select
          id={`${formId}-service`}
          name="service"
          required
          defaultValue=""
          className="border border-gk-steel bg-gk-black px-4 py-3 text-sm text-gk-white outline-none focus:border-gk-orange"
        >
          <option value="" disabled>
            Select a system
          </option>
          {SERVICES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor={`${formId}-budget`} className="font-mono-tech text-xs uppercase tracking-[0.12em] text-gk-grey">
          Budget Range
        </label>
        <select
          id={`${formId}-budget`}
          name="budget"
          defaultValue=""
          className="border border-gk-steel bg-gk-black px-4 py-3 text-sm text-gk-white outline-none focus:border-gk-orange"
        >
          <option value="" disabled>
            Select a range
          </option>
          {BUDGETS.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-2 sm:col-span-2">
        <label htmlFor={`${formId}-description`} className="font-mono-tech text-xs uppercase tracking-[0.12em] text-gk-grey">
          Project Description <span className="text-gk-orange">*</span>
        </label>
        <textarea
          id={`${formId}-description`}
          name="description"
          required
          rows={5}
          className="border border-gk-steel bg-gk-black px-4 py-3 text-sm text-gk-white outline-none focus:border-gk-orange"
        />
      </div>

      <fieldset className="sm:col-span-2">
        <legend className="font-mono-tech mb-3 text-xs uppercase tracking-[0.12em] text-gk-grey">
          Preferred Contact Method
        </legend>
        <div className="flex flex-wrap gap-4">
          {CONTACT_METHODS.map((method, i) => (
            <label key={method} className="flex items-center gap-2 text-sm text-gk-grey">
              <input type="radio" name="contactMethod" value={method} defaultChecked={i === 0} className="accent-[#ff5a1f]" />
              {method}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="sm:col-span-2">
        <label className="flex items-start gap-3 text-sm text-gk-grey">
          <input type="checkbox" name="privacy" required className="mt-1 accent-[#ff5a1f]" />
          <span>
            I agree to the{" "}
            <a href="/privacy" className="text-gk-orange underline underline-offset-2">
              privacy policy
            </a>{" "}
            and consent to GRIDKEEP contacting me about this project.
          </span>
        </label>
      </div>

      {error && (
        <p role="alert" className="sm:col-span-2 text-sm text-gk-orange">
          {error}
        </p>
      )}

      <div className="sm:col-span-2">
        <button type="submit" disabled={status === "submitting"} className="gk-btn gk-btn-primary w-full justify-center sm:w-auto">
          {status === "submitting" ? "Transmitting..." : "Submit Project Intake"}
        </button>
      </div>
    </form>
  );
}
