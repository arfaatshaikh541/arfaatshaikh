export default function WebGLFallback({ label = "GRIDKEEP" }: { label?: string }) {
  return (
    <div className="flex h-full w-full items-center justify-center bg-black-graphite" role="img" aria-label={`${label} system diagram, static rendering`}>
      <div className="relative h-2/3 w-2/3 max-w-[420px]">
        <div className="absolute inset-0 rounded-full border border-line" />
        <div className="absolute inset-6 rounded-full border border-orange-burnt/60" />
        <div className="absolute inset-[38%] rounded-full bg-orange-primary/70 blur-[6px]" />
        <div className="absolute inset-[42%] rounded-full bg-orange-hot" />
      </div>
    </div>
  );
}
