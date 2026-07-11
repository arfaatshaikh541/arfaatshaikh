export interface ContactPayload {
  name: string;
  email: string;
  company: string;
  phone: string;
  service: string;
  budget: string;
  message: string;
  preferredContact: string;
  agreedToPrivacy: boolean;
  honeypot: string;
}

export type ContactErrors = Partial<Record<keyof ContactPayload, string>>;

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateContactPayload(payload: Partial<ContactPayload>): ContactErrors {
  const errors: ContactErrors = {};

  if (!payload.name || payload.name.trim().length < 2) {
    errors.name = "Enter your full name.";
  }
  if (!payload.email || !EMAIL_PATTERN.test(payload.email)) {
    errors.email = "Enter a valid work email address.";
  }
  if (!payload.company || payload.company.trim().length < 2) {
    errors.company = "Enter your company name.";
  }
  if (!payload.service) {
    errors.service = "Select the service you're interested in.";
  }
  if (!payload.message || payload.message.trim().length < 20) {
    errors.message = "Describe your project in at least 20 characters.";
  }
  if (!payload.preferredContact) {
    errors.preferredContact = "Select a preferred contact method.";
  }
  if (!payload.agreedToPrivacy) {
    errors.agreedToPrivacy = "You must agree to the privacy policy to continue.";
  }

  return errors;
}
