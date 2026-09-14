import { SourceRegistryPanel } from "@/components/source-registry-panel";

export default function SourceRegistryPage() {
  return <>
    <p className="eyebrow">Sources</p>
    <h1 className="page-title">Islamic source registry</h1>
    <p>Every source is registered, licensed, reviewed, and approved before it&apos;s used, with a full provenance trail.</p>
    <SourceRegistryPanel />
  </>;
}
