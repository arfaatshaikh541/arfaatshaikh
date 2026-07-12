import * as THREE from "three";

/** Procedural canvas-drawn textures for technical readouts — no external images, no faces. */

function baseCanvas(size = 512) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#050505";
  ctx.fillRect(0, 0, size, size);
  return { canvas, ctx, size };
}

export function createSchematicTexture(): THREE.CanvasTexture {
  const { canvas, ctx, size } = baseCanvas(512);
  const cx = size / 2;
  const cy = size / 2;

  ctx.strokeStyle = "rgba(255,90,31,0.5)";
  ctx.lineWidth = 1.5;
  for (let r = 40; r < size / 2; r += 44) {
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
  }

  const nodeCount = 14;
  for (let i = 0; i < nodeCount; i++) {
    const angle = (i / nodeCount) * Math.PI * 2;
    const r = 60 + (i % 4) * 40;
    const x = cx + Math.cos(angle) * r;
    const y = cy + Math.sin(angle) * r;
    ctx.strokeStyle = "rgba(255,90,31,0.35)";
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.fillStyle = i % 3 === 0 ? "#ff5a1f" : "#3a3d3f";
    ctx.beginPath();
    ctx.arc(x, y, i % 3 === 0 ? 5 : 3, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.fillStyle = "#ff5a1f";
  ctx.beginPath();
  ctx.arc(cx, cy, 8, 0, Math.PI * 2);
  ctx.fill();

  ctx.strokeStyle = "rgba(244,241,236,0.15)";
  ctx.lineWidth = 1;
  for (let i = 0; i < size; i += 32) {
    ctx.beginPath();
    ctx.moveTo(i, 0);
    ctx.lineTo(i, size);
    ctx.stroke();
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export function createMatrixTexture(rows: Array<{ label: string; value: number }>): THREE.CanvasTexture {
  const width = 640;
  const height = 384;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#0a0a0a";
  ctx.fillRect(0, 0, width, height);

  ctx.font = "600 20px 'IBM Plex Mono', monospace";
  ctx.fillStyle = "#f4f1ec";
  ctx.textBaseline = "middle";

  const rowHeight = height / rows.length;
  rows.forEach((row, i) => {
    const y = rowHeight * i + rowHeight / 2;
    ctx.fillStyle = "#f4f1ec";
    ctx.fillText(row.label.toUpperCase(), 24, y - 12);

    const barX = 24;
    const barW = width - 48;
    const barY = y + 10;
    ctx.strokeStyle = "rgba(244,241,236,0.2)";
    ctx.strokeRect(barX, barY, barW, 6);
    ctx.fillStyle = "#ff5a1f";
    ctx.fillRect(barX, barY, barW * row.value, 6);
  });

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export function createSignatureTexture(initials: string): THREE.CanvasTexture {
  const size = 512;
  const { canvas, ctx, size: s } = baseCanvas(size);
  ctx.strokeStyle = "rgba(255,90,31,0.7)";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(s / 2, s / 2, s / 2 - 20, 0, Math.PI * 2);
  ctx.stroke();

  ctx.font = "700 180px 'Oswald', sans-serif";
  ctx.fillStyle = "#ff5a1f";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(initials, s / 2, s / 2 + 10);

  ctx.font = "500 16px 'IBM Plex Mono', monospace";
  ctx.fillStyle = "rgba(244,241,236,0.6)";
  ctx.textAlign = "center";
  ctx.fillText("SYSTEMS ARCHITECT", s / 2, s - 60);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}
