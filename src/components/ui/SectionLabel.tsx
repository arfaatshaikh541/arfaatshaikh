export default function SectionLabel({ children, index }: { children: React.ReactNode; index?: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="h-px w-6 bg-orange-primary" aria-hidden="true" />
      <p className="gk-eyebrow">{children}</p>
      {index && <span className="gk-section-index ml-auto">{index}</span>}
    </div>
  );
}
