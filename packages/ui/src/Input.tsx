import { InputHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, ...props }, ref) => {
    return (
      <input
        ref={ref}
        aria-invalid={Boolean(error)}
        className={clsx(
          "w-full rounded-md border bg-surface-900 px-3 py-2 text-sm text-surface-50",
          "placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-accent-500",
          error ? "border-red-600" : "border-surface-700",
          className
        )}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";
