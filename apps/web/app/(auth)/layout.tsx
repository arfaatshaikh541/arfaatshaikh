export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="text-lg font-semibold tracking-tight text-ink">
            Client <span className="text-accent">Operations</span> Platform
          </span>
        </div>
        {children}
      </div>
    </div>
  );
}
