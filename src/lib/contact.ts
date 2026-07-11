export const BUDGET_RANGES = [
  "Under $5,000",
  "$5,000 – $15,000",
  "$15,000 – $40,000",
  "$40,000+",
  "Not sure yet",
] as const;

export const CONTACT_METHODS = [
  { value: "email", label: "Email" },
  { value: "phone", label: "Phone" },
  { value: "whatsapp", label: "WhatsApp" },
] as const;

export interface ContactFormValues {
  name: string;
  email: string;
  company: string;
  phone: string;
  service: string;
  budget: string;
  message: string;
  preferredContact: string;
  privacyConsent: boolean;
  // Honeypot field — real users never see or fill this in.
  website: string;
}

export type ContactFormErrors = Partial<Record<keyof ContactFormValues, string>>;

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateContactForm(values: ContactFormValues): ContactFormErrors {
  const errors: ContactFormErrors = {};

  if (!values.name.trim() || values.name.trim().length < 2) {
    errors.name = "Enter your full name.";
  }
  if (!EMAIL_PATTERN.test(values.email.trim())) {
    errors.email = "Enter a valid email address.";
  }
  if (!values.service) {
    errors.service = "Select the service you're interested in.";
  }
  if (!values.budget) {
    errors.budget = "Select an approximate budget range.";
  }
  if (!values.message.trim() || values.message.trim().length < 20) {
    errors.message = "Add a bit more detail about the project (at least 20 characters).";
  }
  if (!values.preferredContact) {
    errors.preferredContact = "Select how you'd prefer to be contacted.";
  }
  if (!values.privacyConsent) {
    errors.privacyConsent = "You must agree to the privacy policy to continue.";
  }
  if (values.website.trim().length > 0) {
    errors.website = "Spam detected.";
  }

  return errors;
}

export function hasErrors(errors: ContactFormErrors): boolean {
  return Object.keys(errors).length > 0;
}
