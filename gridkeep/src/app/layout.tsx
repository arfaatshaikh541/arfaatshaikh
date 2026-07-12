import type { Metadata } from "next";
import { Oswald, Space_Grotesk, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import SiteHeader from "@/components/layout/SiteHeader";
import SiteFooter from "@/components/layout/SiteFooter";
import SmoothScrollProvider from "@/components/layout/SmoothScrollProvider";
import JsonLd from "@/components/ui/JsonLd";
import SceneRootLoader from "@/components/three/SceneRootLoader";
import { organizationSchema, websiteSchema } from "@/lib/schema";
import { SITE } from "@/lib/site";

const displayFont = Oswald({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const sansFont = Space_Grotesk({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const monoFont = IBM_Plex_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE.url),
  title: {
    default: `${SITE.name} — Founder-Led Technology Systems`,
    template: `%s — ${SITE.name}`,
  },
  description: SITE.description,
  keywords: [
    "GRIDKEEP",
    "AI systems",
    "business automation",
    "custom software",
    "cybersecurity",
    "cloud infrastructure",
    "business systems",
    "immersive web experiences",
    "United Arab Emirates technology company",
  ],
  authors: [{ name: SITE.founder }],
  creator: SITE.name,
  openGraph: {
    type: "website",
    url: SITE.url,
    siteName: SITE.name,
    title: `${SITE.name} — Founder-Led Technology Systems`,
    description: SITE.description,
  },
  twitter: {
    card: "summary_large_image",
    title: `${SITE.name} — Founder-Led Technology Systems`,
    description: SITE.description,
  },
  robots: {
    index: true,
    follow: true,
  },
  icons: {
    icon: "/favicon.ico",
  },
};

export const viewport = {
  themeColor: "#050505",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${displayFont.variable} ${sansFont.variable} ${monoFont.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-gk-black text-gk-white">
        <JsonLd data={organizationSchema()} />
        <JsonLd data={websiteSchema()} />
        <a href="#main-content" className="skip-link">
          Skip to main content
        </a>
        <SceneRootLoader />
        <SmoothScrollProvider>
          <SiteHeader />
          <main id="main-content" className="flex-1">
            {children}
          </main>
          <SiteFooter />
        </SmoothScrollProvider>
      </body>
    </html>
  );
}
