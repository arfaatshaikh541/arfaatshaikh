import Link from "next/link";
import type { Project } from "@/types";

const statusStyles: Record<Project["status"], string> = {
  "Client Platform": "text-orange-bright border-orange-bright/40",
  "In Development": "text-orange-hot border-orange-hot/40",
  "Internal Product": "text-muted border-line",
};

export default function ProjectCard({ project }: { project: Project }) {
  return (
    <Link href={`/projects/${project.slug}`} className="gk-card group flex flex-col overflow-hidden">
      <div className="relative flex h-40 flex-col justify-between bg-black-graphite p-4">
        <div className="flex items-center justify-between">
          <div className="flex gap-1.5" aria-hidden="true">
            <span className="h-2 w-2 rounded-full bg-orange-primary/70" />
            <span className="h-2 w-2 rounded-full bg-white/15" />
            <span className="h-2 w-2 rounded-full bg-white/15" />
          </div>
          <span className="font-mono text-[9px] uppercase tracking-widest text-muted">System.UI</span>
        </div>
        <div className="flex flex-1 items-end gap-1.5 pb-2" aria-hidden="true">
          {[40, 65, 30, 80, 50, 90, 35].map((h, i) => (
            <span
              key={i}
              className="w-full bg-gradient-to-t from-orange-burnt to-orange-primary/70 opacity-70 transition-opacity group-hover:opacity-100"
              style={{ height: `${h}%` }}
            />
          ))}
        </div>
      </div>
      <div className="flex flex-1 flex-col p-5">
        <span className={`w-fit border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.1em] ${statusStyles[project.status]}`}>
          {project.status}
        </span>
        <h3 className="mt-3 font-display text-base uppercase tracking-wide text-warmwhite">{project.title}</h3>
        <p className="mt-2 flex-1 text-xs leading-relaxed text-muted">{project.summary}</p>
        <span className="mt-4 inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-orange-primary transition-colors group-hover:text-orange-bright">
          View Project <span className="transition-transform group-hover:translate-x-1">→</span>
        </span>
      </div>
    </Link>
  );
}
