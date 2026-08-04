import { Breadcrumbs, type Crumb } from "@/components/ui/Breadcrumbs";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  crumbs: Crumb[];
}

export function PageHeader({ eyebrow, title, description, crumbs }: PageHeaderProps) {
  return (
    <div className="container-edge border-b border-[var(--color-line)] pb-12 pt-32 md:pt-40">
      <Breadcrumbs crumbs={crumbs} />
      {eyebrow && (
        <p className="mt-8 font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          {eyebrow}
        </p>
      )}
      <h1 className="text-balance mt-4 max-w-4xl font-display text-4xl uppercase leading-[0.95] text-[var(--color-off-white)] sm:text-5xl md:text-6xl">
        {title}
      </h1>
      {description && (
        <p className="mt-6 max-w-2xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          {description}
        </p>
      )}
    </div>
  );
}
