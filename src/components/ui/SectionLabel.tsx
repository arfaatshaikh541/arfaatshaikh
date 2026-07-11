export function SectionLabel({ index, label }: { index?: string; label: string }) {
  return (
    <div className="flex items-center gap-3 font-mono text-xs uppercase tracking-widest2 text-orange">
      {index && <span className="text-muted">{index}</span>}
      <span className="h-px w-8 bg-orange/60" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}
