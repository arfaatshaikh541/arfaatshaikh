import type { InputHTMLAttributes, ReactNode } from "react";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: ReactNode;
}

export function Field({ label, error, hint, id, className = "", ...props }: FieldProps) {
  const inputId = id ?? props.name;
  const describedBy = [hint ? `${inputId}-hint` : null, error ? `${inputId}-error` : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className="field">
      <label htmlFor={inputId}>{label}</label>
      <input id={inputId} className={`input ${className}`.trim()} aria-invalid={Boolean(error)} aria-describedby={describedBy} {...props} />
      {hint ? <div className="field-hint" id={`${inputId}-hint`}>{hint}</div> : null}
      {error ? <div className="field-error" id={`${inputId}-error`} role="alert">{error}</div> : null}
    </div>
  );
}
