export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="text-lg font-semibold text-surface-50">
            Lead<span className="text-accent-500">Flow</span>
          </span>
        </div>
        {children}
      </div>
    </main>
  );
}
