const PRINCIPLES = [
  {
    title: "Understand the business first",
    description:
      "Technical decisions come after understanding what the business actually needs, not before.",
  },
  {
    title: "Build for what's real",
    description:
      "No speculative features, no over-engineering. Software is scoped to the problem in front of it.",
  },
  {
    title: "Security is not optional",
    description:
      "Access control, data handling, and secure architecture are part of the build from the start.",
  },
  {
    title: "Visibility over black boxes",
    description:
      "Automation and AI systems are built so you can see what they're doing and why, not just trust them blindly.",
  },
];

export function PhilosophySection() {
  return (
    <section className="border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="philosophy-heading">
      <div className="container-edge">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          How I Work
        </p>
        <h2 id="philosophy-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          Working Philosophy
        </h2>
      </div>

      <div className="container-edge mt-16 grid gap-px overflow-hidden border border-[var(--color-line)] bg-[var(--color-line)] sm:grid-cols-2">
        {PRINCIPLES.map((principle, index) => (
          <div key={principle.title} className="bg-black p-8">
            <span className="font-mono text-xs text-[var(--color-blood-red)]">
              {String(index + 1).padStart(2, "0")}
            </span>
            <h3 className="mt-3 font-display text-xl uppercase text-[var(--color-off-white)]">
              {principle.title}
            </h3>
            <p className="mt-3 text-sm leading-relaxed text-[var(--color-muted)]">
              {principle.description}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
