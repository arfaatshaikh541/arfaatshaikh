import SceneCanvas from "@/components/three/SceneCanvas";
import PortalMesh from "@/components/three/models/PortalMesh";
import ContactForm from "@/components/ui/ContactForm";

export default function ContactPortal() {
  return (
    <section className="relative border-t border-line bg-black py-20 md:py-28" aria-labelledby="contact-heading">
      <div className="mx-auto grid max-w-[1440px] grid-cols-1 items-center gap-14 px-6 md:grid-cols-2 md:px-10">
        <div className="relative flex aspect-square w-full max-w-[520px] flex-col justify-end overflow-hidden md:mx-0 mx-auto">
          <SceneCanvas camera={{ position: [0, 0, 5], fov: 45 }} posterLabel="GRIDKEEP contact portal">
            <PortalMesh scale={1.1} />
          </SceneCanvas>
          <div
            className="pointer-events-none absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-black via-black/75 to-transparent"
            aria-hidden="true"
          />
          <div className="relative z-10 pb-2">
            <h2 id="contact-heading" className="gk-heading text-3xl text-warmwhite drop-shadow-[0_2px_12px_rgba(0,0,0,0.9)] sm:text-4xl">
              READY TO BUILD
              <br />
              WHAT&rsquo;S <span className="text-orange-primary">NEXT?</span>
            </h2>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-warmwhite/80 drop-shadow-[0_2px_8px_rgba(0,0,0,0.9)]">
              Let&rsquo;s connect and build smarter systems together.
            </p>
          </div>
        </div>

        <ContactForm />
      </div>
    </section>
  );
}
