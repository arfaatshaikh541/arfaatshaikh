"use client";

import { useState } from "react";

type Faq = { question: string; answer: string };

export default function FaqAccordion({ items }: { items: Faq[] }) {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <div className="divide-y divide-gk-graphite border-y border-gk-graphite">
      {items.map((item, i) => {
        const open = openIndex === i;
        return (
          <div key={item.question}>
            <h3>
              <button
                type="button"
                onClick={() => setOpenIndex(open ? null : i)}
                aria-expanded={open}
                aria-controls={`faq-panel-${i}`}
                className="flex w-full items-center justify-between gap-4 py-5 text-left"
              >
                <span className="font-display text-lg text-gk-white">{item.question}</span>
                <span
                  className={`font-mono-tech text-xl text-gk-orange transition-transform ${open ? "rotate-45" : ""}`}
                  aria-hidden="true"
                >
                  +
                </span>
              </button>
            </h3>
            <div id={`faq-panel-${i}`} hidden={!open} className="pb-5 pr-10 text-sm leading-relaxed text-gk-grey">
              {item.answer}
            </div>
          </div>
        );
      })}
    </div>
  );
}
