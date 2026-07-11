import { ButtonLink } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      <span className="font-mono text-xs uppercase tracking-widest2 text-orange">Error 404</span>
      <h1 className="mt-6 font-display text-5xl text-warm md:text-6xl">Route not found in the system.</h1>
      <p className="mt-6 max-w-md text-muted">
        The page you're looking for doesn't exist, or has moved. Check the address, or return
        to a known part of the system.
      </p>
      <div className="mt-10 flex gap-4">
        <ButtonLink href="/">Return home</ButtonLink>
        <ButtonLink href="/contact" variant="secondary">
          Contact GRIDKEEP
        </ButtonLink>
      </div>
    </div>
  );
}
