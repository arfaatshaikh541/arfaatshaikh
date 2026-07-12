import { NextResponse } from "next/server";

type ContactPayload = {
  name?: string;
  email?: string;
  company?: string;
  phone?: string;
  service?: string;
  budget?: string;
  description?: string;
  contactMethod?: string;
  privacy?: string;
};

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export async function POST(request: Request) {
  let payload: ContactPayload;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body." }, { status: 400 });
  }

  const { name, email, service, description, privacy } = payload;

  if (!name?.trim() || !email?.trim() || !service?.trim() || !description?.trim()) {
    return NextResponse.json({ error: "Missing required fields." }, { status: 400 });
  }

  if (!isValidEmail(email)) {
    return NextResponse.json({ error: "Invalid email address." }, { status: 400 });
  }

  if (!privacy) {
    return NextResponse.json({ error: "Privacy agreement is required." }, { status: 400 });
  }

  // Intake is logged server-side. Wiring this to an email/CRM provider
  // (e.g. Resend, SendGrid, HubSpot) is the remaining step to deliver it
  // to hello@gridkeep.com automatically.
  console.info("[GRIDKEEP contact intake]", {
    ...payload,
    receivedAt: new Date().toISOString(),
  });

  return NextResponse.json({ ok: true });
}
