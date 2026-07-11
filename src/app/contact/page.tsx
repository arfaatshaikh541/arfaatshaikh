import { buildMetadata } from "@/lib/seo";
import { breadcrumbSchema, contactPageSchema } from "@/lib/schema";
import JsonLd from "@/components/ui/JsonLd";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import ContactForm from "@/components/ui/ContactForm";
import SceneCanvas from "@/components/three/SceneCanvas";
import PortalMesh from "@/components/three/models/PortalMesh";
import { CONTACT_EMAIL, LOCATION } from "@/lib/constants";

export const metadata = buildMetadata({
  title: "Contact",
  description: "Start a project with GRIDKEEP. Tell us about your systems, and the founder will respond directly.",
  path: "/contact",
});

const crumbs = [
  { name: "Home", path: "/" },
  { name: "Contact", path: "/contact" },
];

export default function ContactPage() {
  return (
    <>
      <JsonLd data={breadcrumbSchema(crumbs)} />
      <JsonLd data={contactPageSchema()} />
      <Breadcrumbs items={crumbs} />

      <section className="relative border-b border-line bg-black py-16 md:py-24">
        <div className="mx-auto grid max-w-[1440px] grid-cols-1 items-center gap-14 px-6 md:grid-cols-2 md:px-10">
          <div className="relative flex aspect-square w-full max-w-[480px] flex-col justify-end overflow-hidden md:mx-0 mx-auto">
            <SceneCanvas eager camera={{ position: [0, 0, 5], fov: 45 }} posterLabel="GRIDKEEP contact portal">
              <PortalMesh scale={1.1} />
            </SceneCanvas>
            <div
              className="pointer-events-none absolute inset-x-0 bottom-0 h-3/4 bg-gradient-to-t from-black via-black/75 to-transparent"
              aria-hidden="true"
            />
            <div className="relative z-10 pb-2">
              <h1 className="gk-heading text-3xl text-warmwhite drop-shadow-[0_2px_12px_rgba(0,0,0,0.9)] sm:text-4xl">
                READY TO BUILD
                <br />
                WHAT&rsquo;S <span className="text-orange-primary">NEXT?</span>
              </h1>
              <p className="mt-4 max-w-sm text-sm leading-relaxed text-warmwhite/80 drop-shadow-[0_2px_8px_rgba(0,0,0,0.9)]">
                Let&rsquo;s connect and build smarter systems together. GRIDKEEP responds directly — no account
                managers in between.
              </p>
              <dl className="mt-6 flex flex-col gap-1.5 font-mono text-xs uppercase tracking-[0.08em] text-warmwhite/70">
                <div className="flex gap-2">
                  <dt className="text-warmwhite/60">Email</dt>
                  <dd>
                    <a href={`mailto:${CONTACT_EMAIL}`} className="text-orange-primary hover:text-orange-bright">
                      {CONTACT_EMAIL}
                    </a>
                  </dd>
                </div>
                <div className="flex gap-2">
                  <dt className="text-warmwhite/60">Location</dt>
                  <dd>{LOCATION}</dd>
                </div>
              </dl>
            </div>
          </div>

          <ContactForm />
        </div>
      </section>
    </>
  );
}
