import { NextResponse } from "next/server";

interface ContactPayload {
  name?: string;
  email?: string;
  company?: string;
  service?: string;
  message?: string;
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export async function POST(request: Request) {
  let body: ContactPayload;

  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body." }, { status: 400 });
  }

  const { name, email, message } = body;

  if (!name || !email || !message || !isValidEmail(email)) {
    return NextResponse.json({ error: "Name, a valid work email, and a project description are required." }, { status: 400 });
  }

  // Delivery is not wired to an email provider in this environment.
  // Connect this handler to your transactional email service (e.g. Resend, Postmark, SES) to deliver submissions.
  console.info("GRIDKEEP contact submission received", { name, email, company: body.company, service: body.service });

  return NextResponse.json({ ok: true });
}
