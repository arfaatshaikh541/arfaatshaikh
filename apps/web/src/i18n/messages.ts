import type { Locale } from "@world-of-islam/shared-types";

const messages = {
  en: {
    brand: "World of Islam", tagline: "Revelation, knowledge and guidance, connected.",
    signIn: "Sign in", register: "Create account", email: "Email address", password: "Password",
    displayName: "Display name", forgotPassword: "Forgot password?", dashboard: "Dashboard",
    organisations: "Organisations", signOut: "Sign out", language: "العربية", createOrganisation: "Create organisation",
    organisationName: "Organisation name", organisationSlug: "Organisation URL name", loading: "Loading…"
  },
  ar: {
    brand: "عالم الإسلام", tagline: "الوحي والمعرفة والهداية، في منظومة مترابطة.",
    signIn: "تسجيل الدخول", register: "إنشاء حساب", email: "البريد الإلكتروني", password: "كلمة المرور",
    displayName: "الاسم الظاهر", forgotPassword: "نسيت كلمة المرور؟", dashboard: "لوحة التحكم",
    organisations: "المؤسسات", signOut: "تسجيل الخروج", language: "English", createOrganisation: "إنشاء مؤسسة",
    organisationName: "اسم المؤسسة", organisationSlug: "المعرّف المختصر للمؤسسة", loading: "جارٍ التحميل…"
  }
} as const;

export function getMessages(locale: Locale) { return messages[locale]; }
