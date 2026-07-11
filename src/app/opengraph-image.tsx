import { ImageResponse } from "next/og";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
          justifyContent: "center",
          padding: "80px",
          background:
            "radial-gradient(circle at 75% 50%, #7A2200 0%, #050505 55%, #000000 100%)",
        }}
      >
        <div
          style={{
            fontSize: 28,
            letterSpacing: 6,
            color: "#FF7A1A",
            textTransform: "uppercase",
            marginBottom: 24,
          }}
        >
          Founder-led technology system
        </div>
        <div style={{ fontSize: 96, color: "#F5F0E8", fontWeight: 700, lineHeight: 1.05 }}>
          GRIDKEEP
        </div>
        <div style={{ fontSize: 34, color: "#F5F0E8", marginTop: 24, maxWidth: 820 }}>
          We build the systems behind the business.
        </div>
      </div>
    ),
    { ...size }
  );
}
