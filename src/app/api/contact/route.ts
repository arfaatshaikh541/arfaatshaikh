import { NextRequest, NextResponse } from "next/server";
import { validateContactForm, hasErrors, type ContactFormValues } from "@/lib/contact";

// Rate limiting: this is an in-memory, per-instance sliding window. It works
// for a single long-lived server process but resets on redeploy and does not
// share state across multiple instances/regions. Before shipping this to a
// multi-instance production deployment, replace this Map with a persistent
// store such as Upstash Redis (@upstash/ratelimit) or Vercel KV, keyed the
// same way (client IP), so limits hold across instances and restarts.
const RATE_LIMIT_WINDOW_MS = 10 * 60 * 1000;
const RATE_LIMIT_MAX_REQUESTS = 5;
const rateLimitStore = new Map<string, number[]>();

function isRateLimited(key: string): boolean {
  const now = Date.now();
  const timestamps = (rateLimitStore.get(key) ?? []).filter(
    (t) => now - t < RATE_LIMIT_WINDOW_MS
  );
  timestamps.push(now);
  rateLimitStore.set(key, timestamps);
  return timestamps.length > RATE_LIMIT_MAX_REQUESTS;
}

/**
 * Sends the contact enquiry via email.
 *
 * PLACEHOLDER — wire this up to a real transactional email provider before
 * going live (Resend, Postmark, SendGrid, or AWS SES all work well with
 * Next.js route handlers). Example with Resend:
 *
 *   import { Resend } from "resend";
 *   const resend = new Resend(process.env.RESEND_API_KEY);
 *   await resend.emails.send({
 *     from: "GRIDKEEP <enquiries@arfaat.com>",
 *     to: siteConfig.email,
 *     replyTo: values.email,
 *     subject: `New enquiry from ${values.name}`,
 *     text: buildEmailBody(values),
 *   });
 *
 * Until a provider is configured, submissions are only logged server-side so
 * local development and the honeypot/rate-limit/validation flow can still be
 * tested end to end.
 */
async function deliverEnquiry(values: ContactFormValues): Promise<void> {
  console.info("[contact] new enquiry received", {
    name: values.name,
    email: values.email,
    company: values.company,
    service: values.service,
    budget: values.budget,
    preferredContact: values.preferredContact,
  });
}

export async function POST(request: NextRequest) {
  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    request.headers.get("x-real-ip") ??
    "unknown";

  if (isRateLimited(ip)) {
    return NextResponse.json(
      { message: "Too many requests. Please try again in a few minutes." },
      { status: 429 }
    );
  }

  let body: Partial<ContactFormValues>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ message: "Invalid request body." }, { status: 400 });
  }

  const values: ContactFormValues = {
    name: String(body.name ?? ""),
    email: String(body.email ?? ""),
    company: String(body.company ?? ""),
    phone: String(body.phone ?? ""),
    service: String(body.service ?? ""),
    budget: String(body.budget ?? ""),
    message: String(body.message ?? ""),
    preferredContact: String(body.preferredContact ?? ""),
    privacyConsent: Boolean(body.privacyConsent),
    website: String(body.website ?? ""),
  };

  const errors = validateContactForm(values);
  if (hasErrors(errors)) {
    // A filled honeypot field is treated as spam and silently rejected with
    // a generic message rather than exposing the honeypot to the client.
    if (errors.website) {
      return NextResponse.json({ message: "Unable to process this submission." }, { status: 400 });
    }
    return NextResponse.json(
      { message: "Please check the form for errors.", errors },
      { status: 422 }
    );
  }

  try {
    await deliverEnquiry(values);
  } catch {
    return NextResponse.json(
      { message: "Something went wrong sending your message. Please try again or email directly." },
      { status: 502 }
    );
  }

  return NextResponse.json({ message: "Thanks — your message has been received." }, { status: 200 });
}
