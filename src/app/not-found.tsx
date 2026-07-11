import { LinkButton } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <section className="flex min-h-[70svh] flex-col items-center justify-center border-b border-line bg-black px-6 py-24 text-center">
      <p className="gk-eyebrow mb-5">System Error 404</p>
      <h1 className="gk-heading text-5xl text-warmwhite sm:text-7xl">
        SIGNAL <span className="text-orange-primary">LOST.</span>
      </h1>
      <p className="mt-6 max-w-md text-sm leading-relaxed text-muted md:text-base">
        The page you&rsquo;re looking for isn&rsquo;t part of the GRIDKEEP system. It may have moved or never
        existed.
      </p>
      <LinkButton href="/" className="mt-9">
        Return To The System →
      </LinkButton>
    </section>
  );
}
