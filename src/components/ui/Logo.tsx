import Link from "next/link";

export default function Logo({ className = "" }: { className?: string }) {
  return (
    <Link href="/" className={`flex items-center gap-2.5 group ${className}`} aria-label="GRIDKEEP home">
      <svg width="26" height="26" viewBox="0 0 26 26" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <path d="M13 0L26 13L13 26L0 13L13 0Z" fill="#FF5A00" />
        <path d="M13 5L21 13L13 21L5 13L13 5Z" fill="#050505" />
        <path d="M13 9L17 13L13 17L9 13L13 9Z" fill="#FFA048" />
      </svg>
      <span className="font-display font-semibold text-lg tracking-wide text-warmwhite uppercase group-hover:text-orange-bright transition-colors">
        GRIDKEEP
      </span>
    </Link>
  );
}
