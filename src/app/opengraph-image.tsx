import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpengraphImage() {
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
          backgroundColor: "#000000",
          backgroundImage:
            "radial-gradient(circle at 75% 50%, rgba(139,0,0,0.55) 0%, rgba(0,0,0,0) 60%)",
        }}
      >
        <div
          style={{
            display: "flex",
            fontSize: 28,
            letterSpacing: 6,
            color: "#ff1a12",
            textTransform: "uppercase",
            fontWeight: 700,
          }}
        >
          Creative Engineer · Founder of GRIDKEEP
        </div>
        <div
          style={{
            display: "flex",
            marginTop: 24,
            fontSize: 108,
            color: "#f2ede7",
            fontWeight: 800,
            textTransform: "uppercase",
            letterSpacing: -2,
          }}
        >
          Arfaat Shaikh
        </div>
        <div
          style={{
            display: "flex",
            marginTop: 28,
            fontSize: 30,
            color: "#8e8580",
          }}
        >
          AI · Automation · Software · Security · Cloud · Web
        </div>
      </div>
    ),
    { ...size }
  );
}
