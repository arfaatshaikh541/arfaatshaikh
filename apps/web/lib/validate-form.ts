import type { FieldValues, UseFormSetError, Path } from "react-hook-form";
import type { ZodType } from "zod";

/**
 * Validates `data` against `schema` and, on failure, applies each issue to
 * the react-hook-form instance via setError. Returns the parsed, typed data
 * on success or null on failure -- callers should bail out (not call the
 * API) when null is returned.
 *
 * This performs the validation react-hook-form's `resolver` option would
 * normally do. It is implemented manually here rather than via
 * @hookform/resolvers/zod because the installed zod 4 + resolvers 5
 * combination has a confirmed bug in this environment: resolver-driven
 * `trigger()` correctly reports the form as invalid, but never populates
 * `formState.errors`, silently swallowing every validation error. Calling
 * schema.safeParse directly and feeding react-hook-form's own `setError`
 * API sidesteps the broken adapter entirely.
 */
export function validateWithZod<T extends FieldValues>(
  schema: ZodType<T>,
  data: unknown,
  setError: UseFormSetError<T>
): T | null {
  const result = schema.safeParse(data);
  if (result.success) {
    return result.data;
  }
  for (const issue of result.error.issues) {
    const path = issue.path.join(".") as Path<T>;
    setError(path, { type: issue.code, message: issue.message });
  }
  return null;
}
