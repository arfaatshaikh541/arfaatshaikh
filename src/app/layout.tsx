import type { Metadata } from "next";
import { displayFont, bodyFont, monoFont } from "@/lib/fonts";
import { buildMetadata } from "@/lib/seo";
import { organizationSchema, websiteSchema } from "@/lib/schema";
import SmoothScroll from "@/components/providers/SmoothScroll";
import Header from "@/components/navigation/Header";
import Footer from "@/components/navigation/Footer";
import SkipLink from "@/components/ui/SkipLink";
import "@/styles/globals.css";

export const metadata: Metadata = buildMetadata({
  title: "Systems Behind The Business",
  path: "/",
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${displayFont.variable} ${bodyFont.variable} ${monoFont.variable}`}>
      <body>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationSchema()) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteSchema()) }}
        />
        <SkipLink />
        <SmoothScroll>
          <Header />
          <main id="main-content">{children}</main>
          <Footer />
        </SmoothScroll>
      </body>
    </html>
  );
}
