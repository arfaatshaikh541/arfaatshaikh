import { NextResponse, type NextRequest } from "next/server";
import { validateContactPayload, type ContactPayload } from "@/lib/contactValidation";
import { CONTACT_EMAIL } from "@/lib/constants";

// In-memory rate limiting. This resets whenever the serverless function cold-starts,
// so it only protects against rapid bursts within a warm instance. For durable
// rate limiting across instances, replace this with a shared store (e.g. Upstash
// Redis) keyed the same way.
const submissionLog = new Map<string, number[]>();
const RATE_LIMIT_WINDOW_MS = 10 * 60 * 1000;
const RATE_LIMIT_MAX_REQUESTS = 5;

function isRateLimited(identifier: string) {
  const now = Date.now();
  const timestamps = (submissionLog.get(identifier) ?? []).filter(
    (timestamp) => now - timestamp < RATE_LIMIT_WINDOW_MS
  );
  timestamps.push(now);
  submissionLog.set(identifier, timestamps);
  return timestamps.length > RATE_LIMIT_MAX_REQUESTS;
}

async function deliverContactSubmission(payload: ContactPayload) {
  // Email delivery placeholder. GRIDKEEP does not depend on a paid third-party
  // form service. To activate real delivery, wire this function to a transactional
  // email provider (e.g. Resend, Postmark, or SMTP via nodemailer) using environment
  // variables — never hardcode credentials here.
  //
  // Example (Resend):
  //   await resend.emails.send({
  //     from: "GRIDKEEP <noreply@gridkeep.com>",
  //     to: process.env.CONTACT_RECIPIENT_EMAIL ?? CONTACT_EMAIL,
  //     subject: `New project inquiry — ${payload.company}`,
  //     text: JSON.stringify(payload, null, 2),
  //   });
  if (process.env.NODE_ENV !== "production") {
    console.info(`[GRIDKEEP contact] New inquiry destined for ${CONTACT_EMAIL}:`, payload);
  }
}

export async function POST(request: NextRequest) {
  let body: Partial<ContactPayload>;

  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ message: "Invalid request body." }, { status: 400 });
  }

  // Honeypot: bots tend to fill every field, including ones hidden from real users.
  if (body.honeypot) {
    return NextResponse.json({ message: "Thank you. We'll be in touch." }, { status: 200 });
  }

  const identifier = request.headers.get("x-forwarded-for") ?? "unknown";
  if (isRateLimited(identifier)) {
    return NextResponse.json(
      { message: "Too many submissions. Please try again later." },
      { status: 429 }
    );
  }

  const errors = validateContactPayload(body);
  if (Object.keys(errors).length > 0) {
    return NextResponse.json({ message: "Please correct the highlighted fields.", errors }, { status: 422 });
  }

  try {
    await deliverContactSubmission(body as ContactPayload);
  } catch (error) {
    console.error("[GRIDKEEP contact] Failed to deliver submission:", error);
    return NextResponse.json(
      { message: "We couldn't process your request. Please email us directly." },
      { status: 500 }
    );
  }

  return NextResponse.json({ message: "Submission received." }, { status: 200 });
}
