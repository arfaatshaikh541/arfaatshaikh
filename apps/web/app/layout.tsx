import type { Metadata } from "next";

import { AuthProvider } from "@/lib/auth-context";
import { QueryProvider } from "@/lib/query-client";

import "./globals.css";

export const metadata: Metadata = {
  title: "GRIDKEEP Cyber OS",
  description: "Discover everything. Protect continuously. Respond automatically. Recover confidently.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <QueryProvider>
          <AuthProvider>{children}</AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
