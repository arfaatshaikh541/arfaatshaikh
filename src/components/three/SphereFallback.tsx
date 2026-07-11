export function SphereFallback() {
  return (
    <div
      aria-hidden="true"
      className="hero-fallback absolute inset-0 flex items-center justify-center overflow-hidden"
    >
      <div
        className="h-[42vmin] w-[42vmin] rounded-full"
        style={{
          background:
            "radial-gradient(circle at 42% 38%, rgba(255,59,32,0.25), rgba(10,2,2,0.9) 55%, #000 75%)",
          boxShadow:
            "0 0 120px 40px rgba(139,0,0,0.25), inset 0 0 60px 20px rgba(0,0,0,0.9)",
        }}
      />
    </div>
  );
}
