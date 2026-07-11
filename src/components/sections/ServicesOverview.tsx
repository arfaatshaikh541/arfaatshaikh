import { services } from "@/data/services";
import { LinkButton } from "@/components/ui/Button";
import SectionLabel from "@/components/ui/SectionLabel";
import ServiceCard from "@/components/ui/ServiceCard";

export default function ServicesOverview() {
  const homepageServices = services.slice(0, 6);

  return (
    <section className="relative border-t border-line bg-black-near py-20 md:py-28" aria-labelledby="services-heading">
      <div className="mx-auto max-w-[1440px] px-6 md:px-10">
        <div className="grid grid-cols-1 gap-10 md:grid-cols-[0.85fr_2fr] md:gap-14">
          <div>
            <SectionLabel>Services</SectionLabel>
            <h2 id="services-heading" className="gk-heading mt-5 text-4xl text-warmwhite sm:text-5xl">
              TECHNOLOGY SYSTEMS THAT DRIVE BUSINESS <span className="text-orange-primary">FORWARD.</span>
            </h2>
            <p className="mt-5 max-w-sm text-sm leading-relaxed text-muted">
              From AI and automation to cybersecurity and cloud infrastructure, we build connected systems that
              power modern businesses.
            </p>
            <LinkButton href="/services" variant="secondary" className="mt-8">
              View All Services →
            </LinkButton>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {homepageServices.map((service) => (
              <ServiceCard key={service.slug} service={service} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
