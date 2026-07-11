import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";
import { CtaLink } from "@/components/ui/CtaLink";

export const metadata: Metadata = buildMetadata({
  title: "Page Not Found",
  description: "The page you're looking for doesn't exist or has moved.",
  path: "/404",
  noIndex: true,
});

export default function NotFound() {
  return (
    <section className="container-edge flex min-h-[80vh] flex-col items-start justify-center border-b border-[var(--color-line)] py-32">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
        Error
      </p>
      <h1 className="mt-4 font-display text-[6rem] uppercase leading-[0.85] text-[var(--color-off-white)] sm:text-[9rem] md:text-[12rem]">
        404
      </h1>
      <p className="mt-6 max-w-xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
        This page doesn&apos;t exist, or it has moved. Let&apos;s get you back
        to solid ground.
      </p>
      <div className="mt-10">
        <CtaLink href="/" variant="primary">
          Back to home
        </CtaLink>
      </div>
    </section>
  );
}
