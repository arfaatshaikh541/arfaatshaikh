"use client";

import { useId, useState, type FormEvent } from "react";
import { services } from "@/data/services";
import {
  BUDGET_RANGES,
  CONTACT_METHODS,
  validateContactForm,
  hasErrors,
  type ContactFormValues,
  type ContactFormErrors,
} from "@/lib/contact";
import { cn } from "@/lib/utils";

const initialValues: ContactFormValues = {
  name: "",
  email: "",
  company: "",
  phone: "",
  service: "",
  budget: "",
  message: "",
  preferredContact: "",
  privacyConsent: false,
  website: "",
};

type Status = "idle" | "submitting" | "success" | "error";

const fieldClass =
  "w-full border border-[var(--color-line)] bg-black px-4 py-3 text-sm text-[var(--color-off-white)] outline-none transition-colors focus:border-[var(--color-blood-red)]";
const labelClass = "font-mono text-xs uppercase tracking-[0.12em] text-[var(--color-muted)]";
const errorClass = "mt-1 text-xs text-[var(--color-hot-red,#ff3b20)]";

export function ContactForm() {
  const [values, setValues] = useState<ContactFormValues>(initialValues);
  const [errors, setErrors] = useState<ContactFormErrors>({});
  const [status, setStatus] = useState<Status>("idle");
  const [serverMessage, setServerMessage] = useState<string | null>(null);
  const formId = useId();

  const update = <K extends keyof ContactFormValues>(key: K, value: ContactFormValues[K]) => {
    setValues((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const validationErrors = validateContactForm(values);
    setErrors(validationErrors);

    if (hasErrors(validationErrors)) {
      setStatus("error");
      setServerMessage("Please fix the highlighted fields and try again.");
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

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setStatus("error");
        setServerMessage(
          data?.message ?? "Something went wrong sending your message. Please try again or email directly."
        );
        return;
      }

      setStatus("success");
      setValues(initialValues);
      setServerMessage(null);
    } catch {
      setStatus("error");
      setServerMessage("Network error — please try again or email directly.");
    }
  };

  if (status === "success") {
    return (
      <div
        role="status"
        className="border border-[var(--color-line)] bg-[var(--color-surface)] p-8"
      >
        <p className="font-mono text-xs uppercase tracking-[0.15em] text-[var(--color-blood-red)]">
          Message sent
        </p>
        <p className="mt-4 max-w-md text-lg text-[var(--color-off-white)]">
          Thanks — your message has been received. I read every enquiry personally and will
          reply as soon as I can.
        </p>
      </div>
    );
  }

  return (
    <form noValidate onSubmit={handleSubmit} className="space-y-8">
      {/* Honeypot field: hidden from real users via CSS, bots that fill every
          field will trip this and get silently rejected server-side. */}
      <div aria-hidden="true" className="absolute left-[-9999px] top-auto h-0 w-0 overflow-hidden">
        <label htmlFor={`${formId}-website`}>Website</label>
        <input
          id={`${formId}-website`}
          name="website"
          type="text"
          tabIndex={-1}
          autoComplete="off"
          value={values.website}
          onChange={(e) => update("website", e.target.value)}
        />
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <label className={labelClass} htmlFor={`${formId}-name`}>
            Name *
          </label>
          <input
            id={`${formId}-name`}
            name="name"
            type="text"
            required
            autoComplete="name"
            value={values.name}
            onChange={(e) => update("name", e.target.value)}
            aria-invalid={Boolean(errors.name)}
            aria-describedby={errors.name ? `${formId}-name-error` : undefined}
            className={cn(fieldClass, "mt-2")}
          />
          {errors.name && (
            <p id={`${formId}-name-error`} className={errorClass}>
              {errors.name}
            </p>
          )}
        </div>

        <div>
          <label className={labelClass} htmlFor={`${formId}-email`}>
            Email *
          </label>
          <input
            id={`${formId}-email`}
            name="email"
            type="email"
            required
            autoComplete="email"
            value={values.email}
            onChange={(e) => update("email", e.target.value)}
            aria-invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? `${formId}-email-error` : undefined}
            className={cn(fieldClass, "mt-2")}
          />
          {errors.email && (
            <p id={`${formId}-email-error`} className={errorClass}>
              {errors.email}
            </p>
          )}
        </div>

        <div>
          <label className={labelClass} htmlFor={`${formId}-company`}>
            Company
          </label>
          <input
            id={`${formId}-company`}
            name="company"
            type="text"
            autoComplete="organization"
            value={values.company}
            onChange={(e) => update("company", e.target.value)}
            className={cn(fieldClass, "mt-2")}
          />
        </div>

        <div>
          <label className={labelClass} htmlFor={`${formId}-phone`}>
            Phone
          </label>
          <input
            id={`${formId}-phone`}
            name="phone"
            type="tel"
            autoComplete="tel"
            value={values.phone}
            onChange={(e) => update("phone", e.target.value)}
            className={cn(fieldClass, "mt-2")}
          />
        </div>

        <div>
          <label className={labelClass} htmlFor={`${formId}-service`}>
            Service *
          </label>
          <select
            id={`${formId}-service`}
            name="service"
            required
            value={values.service}
            onChange={(e) => update("service", e.target.value)}
            aria-invalid={Boolean(errors.service)}
            aria-describedby={errors.service ? `${formId}-service-error` : undefined}
            className={cn(fieldClass, "mt-2")}
          >
            <option value="">Select a service</option>
            {services.map((service) => (
              <option key={service.slug} value={service.slug}>
                {service.shortName}
              </option>
            ))}
            <option value="other">Something else</option>
          </select>
          {errors.service && (
            <p id={`${formId}-service-error`} className={errorClass}>
              {errors.service}
            </p>
          )}
        </div>

        <div>
          <label className={labelClass} htmlFor={`${formId}-budget`}>
            Budget range *
          </label>
          <select
            id={`${formId}-budget`}
            name="budget"
            required
            value={values.budget}
            onChange={(e) => update("budget", e.target.value)}
            aria-invalid={Boolean(errors.budget)}
            aria-describedby={errors.budget ? `${formId}-budget-error` : undefined}
            className={cn(fieldClass, "mt-2")}
          >
            <option value="">Select a range</option>
            {BUDGET_RANGES.map((range) => (
              <option key={range} value={range}>
                {range}
              </option>
            ))}
          </select>
          {errors.budget && (
            <p id={`${formId}-budget-error`} className={errorClass}>
              {errors.budget}
            </p>
          )}
        </div>
      </div>

      <div>
        <label className={labelClass} htmlFor={`${formId}-message`}>
          Project description *
        </label>
        <textarea
          id={`${formId}-message`}
          name="message"
          required
          rows={6}
          value={values.message}
          onChange={(e) => update("message", e.target.value)}
          aria-invalid={Boolean(errors.message)}
          aria-describedby={errors.message ? `${formId}-message-error` : undefined}
          className={cn(fieldClass, "mt-2 resize-y")}
          placeholder="What are you trying to build or fix? The more context, the better."
        />
        {errors.message && (
          <p id={`${formId}-message-error`} className={errorClass}>
            {errors.message}
          </p>
        )}
      </div>

      <fieldset>
        <legend className={labelClass}>Preferred contact method *</legend>
        <div className="mt-3 flex flex-wrap gap-6">
          {CONTACT_METHODS.map((method) => (
            <label
              key={method.value}
              className="flex items-center gap-2 text-sm text-[var(--color-off-white)]"
            >
              <input
                type="radio"
                name="preferredContact"
                value={method.value}
                checked={values.preferredContact === method.value}
                onChange={(e) => update("preferredContact", e.target.value)}
                className="h-4 w-4 accent-[var(--color-blood-red)]"
              />
              {method.label}
            </label>
          ))}
        </div>
        {errors.preferredContact && <p className={errorClass}>{errors.preferredContact}</p>}
      </fieldset>

      <div>
        <label className="flex items-start gap-3 text-sm text-[var(--color-muted)]">
          <input
            type="checkbox"
            name="privacyConsent"
            checked={values.privacyConsent}
            onChange={(e) => update("privacyConsent", e.target.checked)}
            className="mt-1 h-4 w-4 accent-[var(--color-blood-red)]"
            aria-invalid={Boolean(errors.privacyConsent)}
          />
          <span>
            I agree to the{" "}
            <a href="/privacy" className="text-[var(--color-off-white)] underline decoration-[var(--color-blood-red)] underline-offset-4">
              Privacy Policy
            </a>{" "}
            and consent to being contacted about my enquiry. *
          </span>
        </label>
        {errors.privacyConsent && <p className={errorClass}>{errors.privacyConsent}</p>}
      </div>

      {status === "error" && serverMessage && (
        <p role="alert" className="border border-[var(--color-hot-red,#ff3b20)] p-4 text-sm text-[var(--color-off-white)]">
          {serverMessage}
        </p>
      )}

      <button
        type="submit"
        disabled={status === "submitting"}
        className="inline-flex items-center gap-3 border border-[var(--color-blood-red)] bg-[var(--color-blood-red)] px-8 py-4 font-mono text-xs uppercase tracking-[0.15em] text-black transition-colors hover:bg-transparent hover:text-[var(--color-blood-red)] disabled:cursor-not-allowed disabled:opacity-60"
      >
        {status === "submitting" ? "Sending…" : "Send message"}
      </button>
    </form>
  );
}
