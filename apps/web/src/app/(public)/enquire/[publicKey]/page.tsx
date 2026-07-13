"use client";

import { Alert, Button, Card, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api-client";
import type { QualificationQuestionOut } from "@/lib/types";

interface PublicServiceOut {
  id: string;
  name: string;
  description: string | null;
}

interface PublicFormConfigOut {
  tenant_name: string;
  brand_primary_color: string;
  brand_secondary_color: string;
  logo_url: string | null;
  services: PublicServiceOut[];
  questions: QualificationQuestionOut[];
  privacy_text: string | null;
}

interface SubmitResponse {
  reference_number: string | null;
  message: string;
}

export default function PublicEnquiryPage() {
  return (
    <Suspense fallback={null}>
      <PublicEnquiryForm />
    </Suspense>
  );
}

function isQuestionVisible(
  question: QualificationQuestionOut,
  answers: Record<string, string | string[]>
): boolean {
  if (question.rules.length === 0) return true;
  return question.rules.every((rule) => {
    const dependsOnValue = answers[rule.depends_on_question_id];
    const current = Array.isArray(dependsOnValue) ? dependsOnValue.join(",") : dependsOnValue;
    return (current ?? "").toLowerCase() === rule.depends_on_value.toLowerCase();
  });
}

function QuestionField({
  question,
  value,
  onChange,
}: {
  question: QualificationQuestionOut;
  value: string | string[] | undefined;
  onChange: (value: string | string[]) => void;
}) {
  const field = question.field_definition;
  const inputId = `question-${question.id}`;

  if (field.field_type === "long_text") {
    return (
      <textarea
        id={inputId}
        rows={3}
        className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
        required={question.is_required}
      />
    );
  }
  if (field.field_type === "single_select") {
    return (
      <select
        id={inputId}
        className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
        required={question.is_required}
      >
        <option value="">Select…</option>
        {field.options.map((o) => (
          <option key={o.value} value={o.label}>
            {o.label}
          </option>
        ))}
      </select>
    );
  }
  if (field.field_type === "multi_select") {
    const selected = (value as string[]) ?? [];
    return (
      <div className="space-y-1">
        {field.options.map((o) => (
          <label key={o.value} className="flex items-center gap-2 text-sm text-surface-300">
            <input
              type="checkbox"
              checked={selected.includes(o.label)}
              onChange={(e) => {
                const next = e.target.checked
                  ? [...selected, o.label]
                  : selected.filter((v) => v !== o.label);
                onChange(next);
              }}
            />
            {o.label}
          </label>
        ))}
      </div>
    );
  }
  if (field.field_type === "yes_no") {
    return (
      <div className="flex gap-4">
        {["Yes", "No"].map((option) => (
          <label key={option} className="flex items-center gap-2 text-sm text-surface-300">
            <input
              type="radio"
              name={inputId}
              checked={value === option}
              onChange={() => onChange(option)}
              required={question.is_required}
            />
            {option}
          </label>
        ))}
      </div>
    );
  }
  if (field.field_type === "checkbox") {
    return (
      <label className="flex items-center gap-2 text-sm text-surface-300">
        <input
          type="checkbox"
          checked={value === "true"}
          onChange={(e) => onChange(e.target.checked ? "true" : "false")}
        />
        Yes
      </label>
    );
  }

  const inputType =
    field.field_type === "email"
      ? "email"
      : field.field_type === "phone"
        ? "tel"
        : field.field_type === "number" || field.field_type === "currency"
          ? "number"
          : field.field_type === "date"
            ? "date"
            : "text";

  return (
    <Input
      id={inputId}
      type={inputType}
      value={(value as string) ?? ""}
      onChange={(e) => onChange(e.target.value)}
      required={question.is_required}
    />
  );
}

function PublicEnquiryForm() {
  const params = useParams<{ publicKey: string }>();
  const searchParams = useSearchParams();
  const publicKey = params.publicKey;

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [company, setCompany] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [preferredContact, setPreferredContact] = useState("");
  const [consent, setConsent] = useState(false);
  const [honeypot, setHoneypot] = useState("");
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [result, setResult] = useState<SubmitResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const configQuery = useQuery({
    queryKey: ["public-form", publicKey],
    queryFn: () => apiFetch<PublicFormConfigOut>(`/public/${publicKey}/form`, { withTenant: false }),
    enabled: Boolean(publicKey),
  });

  // Stable for the lifetime of this form view, so a network retry or a
  // double click on submit can't create two leads.
  const [idempotencyKey] = useState(() => `web-${Math.random().toString(36).slice(2)}-${Date.now()}`);

  useEffect(() => {
    if (configQuery.data) {
      document.title = `Enquire — ${configQuery.data.tenant_name}`;
    }
  }, [configQuery.data]);

  const submitMutation = useMutation({
    mutationFn: () =>
      apiFetch<SubmitResponse>(`/public/${publicKey}/submit`, {
        method: "POST",
        withTenant: false,
        headers: { "Idempotency-Key": idempotencyKey },
        body: {
          first_name: firstName,
          last_name: lastName,
          email: email || null,
          phone: phone || null,
          company: company || null,
          service_id: serviceId || null,
          preferred_contact_method: preferredContact || null,
          consent_given: consent,
          website: honeypot,
          answers: Object.entries(answers)
            .filter(([, v]) => (Array.isArray(v) ? v.length > 0 : v !== ""))
            .map(([question_id, value]) => ({ question_id, value })),
          utm_source: searchParams.get("utm_source"),
          utm_medium: searchParams.get("utm_medium"),
          utm_campaign: searchParams.get("utm_campaign"),
          utm_term: searchParams.get("utm_term"),
          utm_content: searchParams.get("utm_content"),
          referrer_url: typeof document !== "undefined" ? document.referrer || null : null,
        },
      }),
    onSuccess: (data) => setResult(data),
    onError: () => setError("We couldn't submit your enquiry. Please try again."),
  });

  if (configQuery.isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-surface-400">Loading…</p>
      </main>
    );
  }

  if (configQuery.isError || !configQuery.data) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <Alert tone="error">This form is not available.</Alert>
      </main>
    );
  }

  const config = configQuery.data;

  if (result) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <Card className="max-w-md text-center">
          <h1 className="mb-2 text-lg font-semibold text-surface-50">{result.message}</h1>
          {result.reference_number ? (
            <p className="text-sm text-surface-400">
              Your reference number is <span className="font-mono">{result.reference_number}</span>
            </p>
          ) : null}
        </Card>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg">
        <div className="mb-6 flex items-center gap-3">
          {config.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={config.logo_url} alt={config.tenant_name} className="h-8 w-8 rounded" />
          ) : null}
          <h1 className="text-lg font-semibold text-surface-50">{config.tenant_name}</h1>
        </div>
        <Card>
          {error ? (
            <Alert tone="error" className="mb-4">
              {error}
            </Alert>
          ) : null}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setError(null);
              submitMutation.mutate();
            }}
            noValidate
          >
            {/* Honeypot field: real visitors never see or fill this in. */}
            <div className="hidden" aria-hidden="true">
              <label htmlFor="website">Website</label>
              <input
                id="website"
                name="website"
                tabIndex={-1}
                autoComplete="off"
                value={honeypot}
                onChange={(e) => setHoneypot(e.target.value)}
              />
            </div>

            <div className="mb-4 grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="first-name">First name</Label>
                <Input
                  id="first-name"
                  required
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="last-name">Last name</Label>
                <Input id="last-name" value={lastName} onChange={(e) => setLastName(e.target.value)} />
              </div>
            </div>
            <div className="mb-4 grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="phone">Phone</Label>
                <Input id="phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
              </div>
            </div>
            <div className="mb-4">
              <Label htmlFor="company">Company</Label>
              <Input id="company" value={company} onChange={(e) => setCompany(e.target.value)} />
            </div>
            <div className="mb-4">
              <Label htmlFor="service">Which service do you require?</Label>
              <select
                id="service"
                className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                value={serviceId}
                onChange={(e) => setServiceId(e.target.value)}
              >
                <option value="">Select a service…</option>
                {config.services.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>

            {config.questions
              .filter((q) => isQuestionVisible(q, answers))
              .map((question) => (
                <div key={question.id} className="mb-4">
                  <Label htmlFor={`question-${question.id}`}>
                    {question.field_definition.label}
                    {question.is_required ? <span className="ml-1 text-accent-500">*</span> : null}
                  </Label>
                  {question.help_text ? (
                    <p className="mb-1 text-xs text-surface-500">{question.help_text}</p>
                  ) : null}
                  <QuestionField
                    question={question}
                    value={answers[question.id]}
                    onChange={(value) => setAnswers((prev) => ({ ...prev, [question.id]: value }))}
                  />
                </div>
              ))}

            <div className="mb-4">
              <Label htmlFor="preferred-contact">Preferred contact method</Label>
              <select
                id="preferred-contact"
                className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                value={preferredContact}
                onChange={(e) => setPreferredContact(e.target.value)}
              >
                <option value="">No preference</option>
                <option value="phone">Phone call</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="email">Email</option>
                <option value="online_meeting">Online meeting</option>
              </select>
            </div>

            {config.privacy_text ? (
              <p className="mb-3 text-xs text-surface-500">{config.privacy_text}</p>
            ) : null}
            <label className="mb-6 flex items-start gap-2 text-sm text-surface-300">
              <input
                type="checkbox"
                required
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-1"
              />
              I consent to being contacted about my enquiry.
            </label>

            <Button type="submit" className="w-full" loading={submitMutation.isPending}>
              Submit enquiry
            </Button>
          </form>
        </Card>
      </div>
    </main>
  );
}
