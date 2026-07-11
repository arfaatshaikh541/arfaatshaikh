"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { services } from "@/data/services";
import { BUDGET_RANGES, CONTACT_METHODS } from "@/data/formOptions";
import { validateContactPayload, type ContactErrors, type ContactPayload } from "@/lib/contactValidation";
import { Button } from "@/components/ui/Button";

const INITIAL_STATE: ContactPayload = {
  name: "",
  email: "",
  company: "",
  phone: "",
  service: "",
  budget: BUDGET_RANGES[4],
  message: "",
  preferredContact: "",
  agreedToPrivacy: false,
  honeypot: "",
};

type SubmitStatus = "idle" | "submitting" | "success" | "error";

export function ContactForm() {
  const [values, setValues] = useState<ContactPayload>(INITIAL_STATE);
  const [errors, setErrors] = useState<ContactErrors>({});
  const [status, setStatus] = useState<SubmitStatus>("idle");
  const [serverMessage, setServerMessage] = useState<string | null>(null);

  function update<K extends keyof ContactPayload>(key: K, value: ContactPayload[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationErrors = validateContactPayload(values);
    setErrors(validationErrors);

    if (Object.keys(validationErrors).length > 0) {
      setStatus("idle");
      return;
    }

    setStatus("submitting");
    setServerMessage(null);

    try {
      const response = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });

      const data = await response.json();

      if (!response.ok) {
        setStatus("error");
        setServerMessage(data.message ?? "Something went wrong. Please try again.");
        return;
      }

      setStatus("success");
      setValues(INITIAL_STATE);
    } catch {
      setStatus("error");
      setServerMessage("We couldn't reach the server. Please try again in a moment.");
    }
  }

  if (status === "success") {
    return (
      <div role="status" className="border border-orange/40 bg-surface p-8">
        <span className="font-mono text-xs uppercase tracking-widest2 text-orange">Message sent</span>
        <h2 className="mt-4 font-display text-2xl text-warm">We've received your project details.</h2>
        <p className="mt-3 text-muted">
          GRIDKEEP responds directly — expect a reply within one to two business days.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      <div
        aria-hidden="true"
        style={{ position: "absolute", left: "-9999px", width: 0, height: 0, overflow: "hidden" }}
      >
        <label htmlFor="company_url">Leave this field empty</label>
        <input
          id="company_url"
          name="company_url"
          type="text"
          tabIndex={-1}
          autoComplete="off"
          value={values.honeypot}
          onChange={(event) => update("honeypot", event.target.value)}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Field label="Full name" htmlFor="name" error={errors.name}>
          <input
            id="name"
            name="name"
            type="text"
            required
            value={values.name}
            onChange={(event) => update("name", event.target.value)}
            className={inputClass(!!errors.name)}
            aria-invalid={!!errors.name}
          />
        </Field>

        <Field label="Work email" htmlFor="email" error={errors.email}>
          <input
            id="email"
            name="email"
            type="email"
            required
            value={values.email}
            onChange={(event) => update("email", event.target.value)}
            className={inputClass(!!errors.email)}
            aria-invalid={!!errors.email}
          />
        </Field>

        <Field label="Company" htmlFor="company" error={errors.company}>
          <input
            id="company"
            name="company"
            type="text"
            required
            value={values.company}
            onChange={(event) => update("company", event.target.value)}
            className={inputClass(!!errors.company)}
            aria-invalid={!!errors.company}
          />
        </Field>

        <Field label="Phone (optional)" htmlFor="phone">
          <input
            id="phone"
            name="phone"
            type="tel"
            value={values.phone}
            onChange={(event) => update("phone", event.target.value)}
            className={inputClass(false)}
          />
        </Field>

        <Field label="Service" htmlFor="service" error={errors.service}>
          <select
            id="service"
            name="service"
            required
            value={values.service}
            onChange={(event) => update("service", event.target.value)}
            className={inputClass(!!errors.service)}
            aria-invalid={!!errors.service}
          >
            <option value="">Select a service</option>
            {services.map((service) => (
              <option key={service.slug} value={service.name}>
                {service.name}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Budget range" htmlFor="budget">
          <select
            id="budget"
            name="budget"
            value={values.budget}
            onChange={(event) => update("budget", event.target.value)}
            className={inputClass(false)}
          >
            {BUDGET_RANGES.map((range) => (
              <option key={range} value={range}>
                {range}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <Field label="Project description" htmlFor="message" error={errors.message}>
        <textarea
          id="message"
          name="message"
          required
          rows={5}
          value={values.message}
          onChange={(event) => update("message", event.target.value)}
          className={inputClass(!!errors.message)}
          aria-invalid={!!errors.message}
        />
      </Field>

      <fieldset>
        <legend className="mb-3 font-mono text-xs uppercase tracking-widest2 text-muted">
          Preferred contact method
        </legend>
        <div className="flex gap-6">
          {CONTACT_METHODS.map((method) => (
            <label key={method} className="flex items-center gap-2 text-sm text-warm">
              <input
                type="radio"
                name="preferredContact"
                value={method}
                checked={values.preferredContact === method}
                onChange={(event) => update("preferredContact", event.target.value)}
                className="h-4 w-4 accent-orange"
              />
              {method}
            </label>
          ))}
        </div>
        {errors.preferredContact && (
          <p className="mt-2 text-xs text-orange-bright">{errors.preferredContact}</p>
        )}
      </fieldset>

      <label className="flex items-start gap-3 text-sm text-muted">
        <input
          type="checkbox"
          checked={values.agreedToPrivacy}
          onChange={(event) => update("agreedToPrivacy", event.target.checked)}
          className="mt-1 h-4 w-4 accent-orange"
          aria-invalid={!!errors.agreedToPrivacy}
        />
        <span>
          I agree to the{" "}
          <Link href="/privacy" className="text-orange hover:text-orange-bright">
            Privacy Policy
          </Link>
          .
        </span>
      </label>
      {errors.agreedToPrivacy && <p className="text-xs text-orange-bright">{errors.agreedToPrivacy}</p>}

      <div aria-live="polite">
        {status === "error" && serverMessage && (
          <p className="border border-orange/40 bg-surface p-4 text-sm text-orange-bright">{serverMessage}</p>
        )}
      </div>

      <Button type="submit" disabled={status === "submitting"} className="self-start">
        {status === "submitting" ? "Sending…" : "Send project details"}
      </Button>
    </form>
  );
}

function inputClass(hasError: boolean) {
  return `w-full border bg-black px-4 py-3 text-warm outline-none transition-colors focus:border-orange ${
    hasError ? "border-orange" : "border-line"
  }`;
}

function Field({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-2 block font-mono text-xs uppercase tracking-widest2 text-muted">
        {label}
      </label>
      {children}
      {error && (
        <p className="mt-2 text-xs text-orange-bright" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
