"use client";

import { use, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { PublicService, QualificationQuestion } from "@/lib/types";

interface ServicesResponse {
  tenant_name: string;
  services: PublicService[];
}

interface FormResponse {
  form_id: string | null;
  questions: QualificationQuestion[];
}

function QuestionField({
  question,
  value,
  onChange,
}: {
  question: QualificationQuestion;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const label = (
    <Label>
      {question.label}
      {question.is_required && <span className="text-accent"> *</span>}
    </Label>
  );

  switch (question.question_type) {
    case "long_text":
      return (
        <div>
          {label}
          <textarea
            className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
            rows={3}
            value={(value as string) ?? ""}
            onChange={(e) => onChange(e.target.value)}
          />
        </div>
      );
    case "single_select":
      return (
        <div>
          {label}
          <select
            className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
            value={(value as string) ?? ""}
            onChange={(e) => onChange(e.target.value)}
          >
            <option value="">Select an option</option>
            {question.options.map((option) => (
              <option key={option.id} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      );
    case "yes_no":
      return (
        <div>
          {label}
          <div className="mt-1 flex gap-4 text-sm text-ink-muted">
            <label className="flex items-center gap-2">
              <input type="radio" checked={value === true} onChange={() => onChange(true)} /> Yes
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" checked={value === false} onChange={() => onChange(false)} /> No
            </label>
          </div>
        </div>
      );
    case "date":
      return (
        <div>
          {label}
          <Input type="date" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />
        </div>
      );
    case "number":
    case "currency":
      return (
        <div>
          {label}
          <Input type="number" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />
        </div>
      );
    default:
      return (
        <div>
          {label}
          <Input value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />
        </div>
      );
  }
}

export default function PublicEnquiryPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);

  const [serviceId, setServiceId] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [company, setCompany] = useState("");
  const [consent, setConsent] = useState(false);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [website, setWebsite] = useState(""); // honeypot
  const [validationError, setValidationError] = useState<string | null>(null);

  const servicesQuery = useQuery({
    queryKey: ["public", "services", token],
    queryFn: () => api.get<ServicesResponse>(`/public/capture/${token}/services`),
  });

  const formQuery = useQuery({
    queryKey: ["public", "form", token, serviceId],
    queryFn: () => api.get<FormResponse>(`/public/capture/${token}/form${serviceId ? `?service_id=${serviceId}` : ""}`),
    enabled: Boolean(serviceId),
  });

  const submitMutation = useMutation({
    mutationFn: () =>
      api.post<{ status: string; reference_number?: string }>(`/public/capture/${token}/enquiry`, {
        first_name: firstName,
        last_name: lastName,
        email: email || null,
        phone: phone || null,
        company: company || null,
        service_id: serviceId || null,
        consent_given: consent,
        website,
        answers: Object.entries(answers).map(([question_id, value]) => ({ question_id, value })),
      }),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    if (!firstName.trim()) {
      setValidationError("Please enter your first name.");
      return;
    }
    if (!email.trim() && !phone.trim()) {
      setValidationError("Please provide an email or phone number so we can reach you.");
      return;
    }
    const missingRequired = (formQuery.data?.questions ?? []).find(
      (q) => q.is_required && (answers[q.id] === undefined || answers[q.id] === ""),
    );
    if (missingRequired) {
      setValidationError(`Please answer: "${missingRequired.label}"`);
      return;
    }
    submitMutation.mutate();
  };

  if (servicesQuery.isLoading) {
    return <div className="flex min-h-screen items-center justify-center text-ink-muted">Loading…</div>;
  }

  if (servicesQuery.isError || !servicesQuery.data) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <Alert tone="error">This enquiry form could not be found.</Alert>
      </div>
    );
  }

  if (submitMutation.isSuccess) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface px-4">
        <Card className="max-w-md">
          <CardHeader title="Thank you" />
          <Alert tone="success">
            Your enquiry with {servicesQuery.data.tenant_name} has been received.
            {submitMutation.data.reference_number && (
              <>
                {" "}
                Reference number: <strong>{submitMutation.data.reference_number}</strong>.
              </>
            )}
          </Alert>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface px-4 py-12">
      <div className="mx-auto max-w-lg">
        <h1 className="text-xl font-semibold text-ink">Contact {servicesQuery.data.tenant_name}</h1>
        <p className="mt-1 text-sm text-ink-muted">Tell us about your enquiry and we&apos;ll be in touch shortly.</p>

        <Card className="mt-6">
          <form className="space-y-4" onSubmit={handleSubmit} noValidate>
            {validationError && <Alert tone="error">{validationError}</Alert>}
            {submitMutation.isError && (
              <Alert tone="error">
                {submitMutation.error instanceof ApiError ? submitMutation.error.message : "Unable to submit your enquiry."}
              </Alert>
            )}

            <div>
              <Label>Service</Label>
              <select
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={serviceId}
                onChange={(e) => {
                  setServiceId(e.target.value);
                  setAnswers({});
                }}
              >
                <option value="">Select a service</option>
                {servicesQuery.data.services.map((service) => (
                  <option key={service.id} value={service.id}>
                    {service.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>First name</Label>
                <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} required />
              </div>
              <div>
                <Label>Last name</Label>
                <Input value={lastName} onChange={(e) => setLastName(e.target.value)} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Email</Label>
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div>
                <Label>Phone</Label>
                <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
              </div>
            </div>
            <div>
              <Label>Company</Label>
              <Input value={company} onChange={(e) => setCompany(e.target.value)} />
            </div>

            {/* Honeypot — hidden from real visitors via CSS, left empty by them. */}
            <div className="absolute -left-[9999px]" aria-hidden="true">
              <label>
                Website
                <input tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
              </label>
            </div>

            {formQuery.data?.questions.map((question) => (
              <QuestionField
                key={question.id}
                question={question}
                value={answers[question.id]}
                onChange={(value) => setAnswers((prev) => ({ ...prev, [question.id]: value }))}
              />
            ))}

            <label className="flex items-start gap-2 text-sm text-ink-muted">
              <input type="checkbox" className="mt-1" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              I consent to being contacted regarding this enquiry.
            </label>

            <Button type="submit" className="w-full" disabled={submitMutation.isPending}>
              {submitMutation.isPending ? "Submitting…" : "Submit enquiry"}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
