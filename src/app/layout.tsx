import type { Metadata } from "next";
import { Big_Shoulders, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { SkipLink } from "@/components/layout/SkipLink";
import { SmoothScroll } from "@/components/layout/SmoothScroll";
import { Loader } from "@/components/ui/Loader";
import { ScrollProgress } from "@/components/navigation/ScrollProgress";
import { JsonLd } from "@/components/seo/JsonLd";
import { organizationSchema, websiteSchema } from "@/lib/schema";
import { buildMetadata } from "@/lib/seo";

const displayFont = Big_Shoulders({
  subsets: ["latin"],
  weight: ["600", "700", "800"],
  variable: "--font-display",
  display: "swap",
});

const sansFont = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

const monoFont = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  ...buildMetadata({
    title: "GRIDKEEP — We build the systems behind the business.",
    description:
      "GRIDKEEP is a founder-led technology systems company designing AI, automation, custom software, cybersecurity, cloud infrastructure, and immersive digital experiences.",
    path: "/",
  }),
  metadataBase: new URL("https://gridkeep.com"),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${displayFont.variable} ${sansFont.variable} ${monoFont.variable}`}>
      <body>
        <JsonLd data={[organizationSchema(), websiteSchema()]} />
        <Loader />
        <SkipLink />
        <ScrollProgress />
        <SmoothScroll>
          <Header />
          <main id="main-content">{children}</main>
          <Footer />
        </SmoothScroll>
      </body>
    </html>
  );
}
