import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Newsreader, Noto_Naskh_Arabic } from "next/font/google";
import "./globals.css";

// Self-hosted by Next.js at build time (no runtime request to Google, so the
// existing strict CSP's font-src 'self' still holds unchanged).
const displaySerif = Newsreader({ subsets: ["latin"], variable: "--font-display", display: "swap" });
const arabicSerif = Noto_Naskh_Arabic({ subsets: ["arabic"], variable: "--font-arabic-display", display: "swap" });

export const metadata: Metadata = {
  title: { default: "World of Islam", template: "%s · World of Islam" },
  description: "Revelation, knowledge and guidance, connected.",
  // This app runs at app.arfaat.com/worldofislam behind authentication.
  // The public marketing/overview page lives separately at arfaat.com/worldofislam
  // and carries its own indexable metadata; the application itself must never
  // be indexed or linked from search results.
  robots: { index: false, follow: false, nocache: true },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className={`${displaySerif.variable} ${arabicSerif.variable}`}>
      <body>{children}</body>
    </html>
  );
}
