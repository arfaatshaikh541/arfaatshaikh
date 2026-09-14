import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

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
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
