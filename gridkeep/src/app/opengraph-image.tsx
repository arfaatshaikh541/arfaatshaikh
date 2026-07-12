import { ImageResponse } from "next/og";
import { SITE } from "@/lib/site";

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
          justifyContent: "center",
          padding: "80px",
          background: "#050505",
          backgroundImage:
            "linear-gradient(to right, rgba(255,90,31,0.08) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,90,31,0.08) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      >
        <div style={{ display: "flex", color: "#ff5a1f", fontSize: 22, letterSpacing: 6, fontWeight: 600 }}>
          FOUNDER-LED TECHNOLOGY SYSTEM
        </div>
        <div
          style={{
            display: "flex",
            marginTop: 24,
            fontSize: 88,
            fontWeight: 800,
            color: "#f4f1ec",
            lineHeight: 1.05,
          }}
        >
          WE BUILD THE
        </div>
        <div style={{ display: "flex", fontSize: 88, fontWeight: 800, color: "#ff5a1f", lineHeight: 1.05 }}>
          SYSTEMS
        </div>
        <div style={{ display: "flex", fontSize: 88, fontWeight: 800, color: "#f4f1ec", lineHeight: 1.05 }}>
          BEHIND THE BUSINESS.
        </div>
        <div style={{ display: "flex", marginTop: 40, fontSize: 26, color: "#8a8a86" }}>{SITE.url.replace("https://", "")}</div>
      </div>
    ),
    { ...size }
  );
}
