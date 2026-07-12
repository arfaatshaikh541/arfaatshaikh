"use client";

import dynamic from "next/dynamic";
import Chapter from "./Chapter";

const HeroReactor = dynamic(() => import("@/components/three/prototypes/HeroReactor"), { ssr: false });
const AIInferenceNode = dynamic(() => import("@/components/three/prototypes/AIInferenceNode"), { ssr: false });
const AutomationCell = dynamic(() => import("@/components/three/prototypes/AutomationCell"), { ssr: false });
const SoftwareRack = dynamic(() => import("@/components/three/prototypes/SoftwareRack"), { ssr: false });
const CyberVault = dynamic(() => import("@/components/three/prototypes/CyberVault"), { ssr: false });

const CHAPTERS = [
  {
    number: "01",
    title: "GRIDKEEP Core",
    description:
      "The GRIDKEEP Core Reactor in cutaway: layered structural rings, an armored shutter aperture, and an internal orange energy chamber that stabilizes as the mechanism opens.",
    copy:
      "Every GRIDKEEP engagement is powered by the same operating core: one architecture standard applied across AI, automation, software, security, and infrastructure.",
    labels: ["Structural Rings", "Aperture Shutters", "Energy Core"],
    Prototype: HeroReactor,
    cameraPosition: [0, 0.3, 4.2] as [number, number, number],
  },
  {
    number: "02",
    title: "AI Inference System",
    description:
      "A modular AI inference node with removable compute modules and liquid cooling lines, processing data as it enters through defined input ports.",
    copy:
      "Data enters, compute modules activate in sequence, and orange status pulses trace inference from ingestion to decision — not a black box, a system you can inspect.",
    labels: ["Compute Modules", "Liquid Cooling", "Inference Core"],
    Prototype: AIInferenceNode,
    reverse: true,
    cameraPosition: [2.1, 1, 2.6] as [number, number, number],
  },
  {
    number: "03",
    title: "Automation Cell",
    description:
      "An industrial automation station with a robotic arm, vision camera, and sorting rails, validating and routing work as it arrives.",
    copy:
      "A payload arrives, a sensor scans it, and the robotic arm routes it to acceptance or rejection — every decision logged, every exception visible.",
    labels: ["Vision Camera", "Robotic Arm", "Sorting Rails"],
    Prototype: AutomationCell,
    cameraPosition: [2.8, 1.1, 3.2] as [number, number, number],
  },
  {
    number: "04",
    title: "Software Architecture Rack",
    description:
      "A modular server rack with API gateway, authentication, application services, and database core modules sliding into place.",
    copy:
      "Modules slide into place one at a time, connections illuminate, and the architecture completes — a physical way to see what most teams only diagram.",
    labels: ["API Gateway", "Auth Module", "Database Core"],
    Prototype: SoftwareRack,
    reverse: true,
    cameraPosition: [1.6, 0.6, 2.3] as [number, number, number],
  },
  {
    number: "05",
    title: "Cybersecurity Vault",
    description:
      "An armored security vault with a segmented door, biometric scanner, and hardware security module locking down protected data.",
    copy:
      "A threat object approaches, the scan system activates, and the vault locks — unauthorized input blocked before it ever reaches protected data.",
    labels: ["Biometric Scanner", "HSM", "Segmented Door"],
    Prototype: CyberVault,
    cameraPosition: [1.6, 0.8, 2.3] as [number, number, number],
  },
];

export default function ChaptersSection() {
  return (
    <div aria-label="GRIDKEEP prototype chapters">
      {CHAPTERS.map((chapter) => (
        <Chapter key={chapter.number} {...chapter} />
      ))}
    </div>
  );
}
