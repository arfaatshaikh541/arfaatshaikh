const CAPABILITIES = [
  "Artificial Intelligence",
  "AI Agents",
  "Business Automation",
  "Custom Software",
  "SaaS Development",
  "Web Development",
  "Immersive Web Experiences",
  "Cybersecurity",
  "Cloud Infrastructure",
  "DevOps",
  "CRM & ERP Systems",
  "API Integrations",
  "Data Dashboards",
  "UI/UX & Product Design",
  "Business Process Engineering",
  "Digital Strategy",
];

export function CapabilitiesSection() {
  return (
    <section className="border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="capabilities-heading">
      <div className="container-edge">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Full Range
        </p>
        <h2 id="capabilities-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          Capabilities
        </h2>
      </div>

      <ul className="container-edge mt-12 flex flex-wrap gap-3">
        {CAPABILITIES.map((item) => (
          <li
            key={item}
            className="border border-[var(--color-line)] px-5 py-3 font-mono text-xs uppercase tracking-[0.08em] text-[var(--color-off-white)] transition-colors hover:border-[var(--color-blood-red)] hover:text-[var(--color-blood-red)]"
          >
            {item}
          </li>
        ))}
      </ul>
    </section>
  );
}
