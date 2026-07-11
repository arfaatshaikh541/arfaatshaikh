import { prototypeChapters } from "@/data/prototypes";
import SectionLabel from "@/components/ui/SectionLabel";
import PrototypeCard from "@/components/ui/PrototypeCard";

export default function PrototypeChapters() {
  return (
    <section className="relative border-t border-line bg-black py-20 md:py-24" aria-labelledby="prototypes-heading">
      <div className="mx-auto max-w-[1440px] px-6 md:px-10">
        <SectionLabel index="CH. 01 — 05">Engineering Chapters</SectionLabel>
        <h2 id="prototypes-heading" className="sr-only">
          GRIDKEEP Prototype Chapters
        </h2>
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {prototypeChapters.map((chapter) => (
            <PrototypeCard key={chapter.slug} chapter={chapter} />
          ))}
        </div>
      </div>
    </section>
  );
}
