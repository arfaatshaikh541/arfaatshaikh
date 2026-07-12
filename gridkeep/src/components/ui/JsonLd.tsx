type Props = {
  data: Record<string, unknown>;
};

/** Renders a JSON-LD structured data block. Server-renderable, no hydration cost. */
export default function JsonLd({ data }: Props) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}
