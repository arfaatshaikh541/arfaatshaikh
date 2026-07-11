import { ImageResponse } from "next/og";

export const runtime = "edge";
export const size = { width: 64, height: 64 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#000000",
        }}
      >
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: "50%",
            border: "4px solid #FF5A00",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#FF7A1A" }} />
        </div>
      </div>
    ),
    { ...size }
  );
}
