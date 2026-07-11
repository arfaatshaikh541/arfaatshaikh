import { ImageResponse } from "next/og";

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
          alignItems: "center",
          justifyContent: "center",
          background: "#000000",
          backgroundImage:
            "radial-gradient(circle at 50% 50%, rgba(255,90,0,0.35) 0%, rgba(0,0,0,0) 60%)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          <svg width="72" height="72" viewBox="0 0 26 26" fill="none">
            <path d="M13 0L26 13L13 26L0 13L13 0Z" fill="#FF5A00" />
            <path d="M13 5L21 13L13 21L5 13L13 5Z" fill="#050505" />
            <path d="M13 9L17 13L13 17L9 13L13 9Z" fill="#FFA048" />
          </svg>
          <span style={{ fontSize: 84, color: "#F2EEE8", letterSpacing: -2, fontWeight: 700 }}>GRIDKEEP</span>
        </div>
        <span style={{ marginTop: 28, fontSize: 30, color: "#FF7A1A", letterSpacing: 4 }}>
          SYSTEMS BEHIND THE BUSINESS
        </span>
      </div>
    ),
    { ...size }
  );
}
