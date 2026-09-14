import { redirect } from "next/navigation";
import { defaultLocale } from "@/i18n/config";

// The middleware (src/middleware.ts) redirects any unlocalized path to
// "/{defaultLocale}/...", but the exact site root - which, once a basePath
// is configured, is the deployment's landing URL (e.g. https://app.arfaat.com/worldofislam
// with no trailing segment) - can be served from Next.js's static not-found
// cache before middleware runs. A real page at the root closes that gap.
export default function RootIndex() {
  redirect(`/${defaultLocale}`);
}
