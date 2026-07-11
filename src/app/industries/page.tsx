import { buildMetadata } from "@/lib/seo";
import { breadcrumbSchema } from "@/lib/schema";
import JsonLd from "@/components/ui/JsonLd";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import PageIntro from "@/components/sections/PageIntro";
import ContactPortal from "@/components/sections/ContactPortal";
import { industries } from "@/data/industries";

export const metadata = buildMetadata({
  title: "Industries",
  description: "Industries GRIDKEEP engineers systems for, from professional services to technology and SaaS companies.",
  path: "/industries",
});

const crumbs = [
  { name: "Home", path: "/" },
  { name: "Industries", path: "/industries" },
];

export default function IndustriesPage() {
  return (
    <>
      <JsonLd data={breadcrumbSchema(crumbs)} />
      <Breadcrumbs items={crumbs} />
      <PageIntro
        eyebrow="Industries"
        title={
          <>
            BUILT FOR THE WAY <span className="text-orange-primary">YOUR INDUSTRY OPERATES.</span>
          </>
        }
        description="Every sector runs on different systems and constraints. GRIDKEEP engineers technology around how each business actually operates, not a one-size template."
        model="cluster"
      />

      <section className="border-b border-line bg-black-near py-16 md:py-24" aria-label="Industries served">
        <div className="mx-auto grid max-w-[1440px] grid-cols-1 gap-4 px-6 sm:grid-cols-2 md:px-10 lg:grid-cols-3">
          {industries.map((industry) => (
            <div key={industry.slug} className="gk-card p-6">
              <h2 className="font-display text-lg uppercase tracking-wide text-warmwhite">{industry.title}</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted">{industry.description}</p>
            </div>
          ))}
        </div>
      </section>

      <ContactPortal />
    </>
  );
}
