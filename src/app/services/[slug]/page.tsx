import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";
import { breadcrumbSchema, serviceSchema } from "@/lib/schema";
import JsonLd from "@/components/ui/JsonLd";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import SectionLabel from "@/components/ui/SectionLabel";
import { LinkButton } from "@/components/ui/Button";
import SceneCanvas from "@/components/three/SceneCanvas";
import PrototypeModel from "@/components/three/PrototypeModel";
import ContactPortal from "@/components/sections/ContactPortal";
import { services } from "@/data/services";

interface ServicePageProps {
  params: { slug: string };
}

export function generateStaticParams() {
  return services.map((s) => ({ slug: s.slug }));
}

export function generateMetadata({ params }: ServicePageProps): Metadata {
  const service = services.find((s) => s.slug === params.slug);
  if (!service) return buildMetadata({ title: "Service", path: `/services/${params.slug}` });
  return buildMetadata({
    title: service.title,
    description: service.longDescription,
    path: `/services/${service.slug}`,
  });
}

export default function ServiceDetailPage({ params }: ServicePageProps) {
  const service = services.find((s) => s.slug === params.slug);
  if (!service) notFound();

  const crumbs = [
    { name: "Home", path: "/" },
    { name: "Services", path: "/services" },
    { name: service.title, path: `/services/${service.slug}` },
  ];

  const otherServices = services.filter((s) => s.slug !== service.slug).slice(0, 3);

  return (
    <>
      <JsonLd data={breadcrumbSchema(crumbs)} />
      <JsonLd
        data={serviceSchema({
          name: service.title,
          description: service.longDescription,
          path: `/services/${service.slug}`,
        })}
      />
      <Breadcrumbs items={crumbs} />

      <section className="relative overflow-hidden border-b border-line bg-black pb-16 pt-14 md:pb-24 md:pt-20">
        <div className="pointer-events-none absolute inset-0 bg-grid-lines bg-[size:52px_52px] opacity-[0.25]" aria-hidden="true" />
        <div className="relative mx-auto grid max-w-[1440px] grid-cols-1 items-center gap-10 px-6 md:grid-cols-[1.2fr_0.8fr] md:px-10">
          <div>
            <p className="gk-eyebrow mb-5">Service {service.index}</p>
            <h1 className="gk-heading text-4xl text-warmwhite sm:text-5xl md:text-6xl">{service.title}</h1>
            <p className="mt-6 max-w-xl text-sm leading-relaxed text-muted md:text-base">{service.longDescription}</p>
            <div className="mt-9 flex flex-wrap gap-4">
              <LinkButton href="/contact">Start A Project →</LinkButton>
              <LinkButton href="/services" variant="secondary">
                All Services
              </LinkButton>
            </div>
          </div>
          <div className="relative mx-auto h-[280px] w-full max-w-[420px] md:h-[380px]">
            <SceneCanvas eager camera={{ position: [0, 0, 6.5], fov: 40 }} posterLabel={service.title}>
              <PrototypeModel variant={service.model} scale={0.95} />
            </SceneCanvas>
          </div>
        </div>
      </section>

      <section className="border-b border-line bg-black-near py-16 md:py-24">
        <div className="mx-auto max-w-[1440px] px-6 md:px-10">
          <SectionLabel>Capabilities</SectionLabel>
          <h2 className="gk-heading mt-5 max-w-2xl text-3xl text-warmwhite sm:text-4xl">
            WHAT THIS SYSTEM <span className="text-orange-primary">COVERS.</span>
          </h2>
          <ul className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {service.capabilities.map((cap) => (
              <li key={cap} className="gk-card flex items-start gap-3 p-5">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-orange-primary" aria-hidden="true" />
                <span className="text-sm text-warmwhite/85">{cap}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="border-b border-line bg-black py-16 md:py-24">
        <div className="mx-auto max-w-[1440px] px-6 md:px-10">
          <SectionLabel>Related Services</SectionLabel>
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {otherServices.map((s) => (
              <a
                key={s.slug}
                href={`/services/${s.slug}`}
                className="gk-card flex flex-col gap-2 p-5 transition-colors hover:border-orange-bright/60"
              >
                <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-orange-primary">{s.title}</span>
                <span className="text-xs text-muted">{s.description}</span>
              </a>
            ))}
          </div>
        </div>
      </section>

      <ContactPortal />
    </>
  );
}
