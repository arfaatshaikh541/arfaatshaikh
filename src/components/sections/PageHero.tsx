import type { ReactNode } from "react";
import { Reveal } from "@/components/ui/Reveal";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { cn } from "@/lib/utils";

interface PageHeroProps {
  eyebrow: string;
  title: string;
  description: string;
  children?: ReactNode;
  className?: string;
}

export function PageHero({ eyebrow, title, description, children, className }: PageHeroProps) {
  return (
    <div className={cn("mx-auto max-w-[1600px] px-6 pb-16 pt-10 md:px-10", className)}>
      <Reveal>
        <SectionLabel label={eyebrow} />
      </Reveal>
      <Reveal delay={0.06}>
        <h1 className="mt-6 max-w-3xl text-balance font-display text-4xl text-warm md:text-6xl">
          {title}
        </h1>
      </Reveal>
      <Reveal delay={0.12}>
        <p className="mt-6 max-w-2xl text-balance text-muted md:text-lg">{description}</p>
      </Reveal>
      {children}
    </div>
  );
}
