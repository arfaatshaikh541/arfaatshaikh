import { type InputHTMLAttributes, type ReactNode, forwardRef, useId } from "react";

export interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

export const TextInput = forwardRef<HTMLInputElement, TextInputProps>(
  ({ label, error, hint, id, className = "", ...props }, ref) => {
    const generatedId = useId();
    const inputId = id ?? generatedId;
    const errorId = error ? `${inputId}-error` : undefined;
    const hintId = hint ? `${inputId}-hint` : undefined;

    return (
      <div className="flex flex-col gap-1.5">
        <label htmlFor={inputId} className="text-sm font-medium text-ink-700">
          {label}
        </label>
        <input
          ref={ref}
          id={inputId}
          aria-invalid={Boolean(error) || undefined}
          aria-describedby={[errorId, hintId].filter(Boolean).join(" ") || undefined}
          className={[
            "h-10 rounded border bg-surface-800 px-3 text-sm text-ink-900 placeholder:text-ink-300",
            "focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent",
            error ? "border-severity-critical" : "border-surface-border",
            className,
          ].join(" ")}
          {...props}
        />
        {hint ? (
          <p id={hintId} className="text-xs text-ink-500">
            {hint}
          </p>
        ) : null}
        {error ? (
          <p id={errorId} role="alert" className="text-xs text-severity-critical">
            {error}
          </p>
        ) : null}
      </div>
    );
  },
);
TextInput.displayName = "TextInput";

export function FormRoot({ children, ...props }: { children: ReactNode } & React.FormHTMLAttributes<HTMLFormElement>) {
  return (
    <form noValidate className="flex flex-col gap-4" {...props}>
      {children}
    </form>
  );
}
