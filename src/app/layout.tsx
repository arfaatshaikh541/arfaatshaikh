import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Big_Shoulders } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/navigation/Nav";
import { Footer } from "@/components/layout/Footer";
import { SmoothScrollProvider } from "@/components/layout/SmoothScrollProvider";
import { JsonLd } from "@/components/seo/JsonLd";
import { personSchema, organizationSchema, websiteSchema } from "@/lib/schema";
import { siteConfig } from "@/lib/seo";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
  weight: ["400", "500"],
});

const bigShoulders = Big_Shoulders({
  subsets: ["latin"],
  variable: "--font-big-shoulders",
  display: "swap",
  weight: ["600", "700", "800", "900"],
});

export const metadata: Metadata = {
  metadataBase: new URL(siteConfig.url),
  title: {
    default: siteConfig.title,
    template: "%s | Arfaat Shaikh",
  },
  description: siteConfig.description,
  authors: [{ name: "Arfaat Shaikh", url: siteConfig.url }],
  creator: "Arfaat Shaikh",
  formatDetection: {
    telephone: false,
  },
  icons: {
    icon: "/favicon.ico",
  },
};

export const viewport = {
  themeColor: "#000000",
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
      className={`${inter.variable} ${jetbrainsMono.variable} ${bigShoulders.variable} h-full`}
    >
      <body className="flex min-h-full flex-col bg-black text-[var(--color-off-white)] antialiased">
        <JsonLd data={[personSchema(), organizationSchema(), websiteSchema()]} />
        <a href="#main-content" className="skip-link">
          Skip to content
        </a>
        <SmoothScrollProvider>
          <Nav />
          <main id="main-content" className="flex-1">
            {children}
          </main>
          <Footer />
        </SmoothScrollProvider>
      </body>
    </html>
  );
}
