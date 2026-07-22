# ADR 0004: Manual Zod Validation Instead of @hookform/resolvers

## Status
Accepted (Milestone 1) -- revisit when upgrading react-hook-form/zod

## Context
While writing the first frontend component tests (`app/register/__tests__/register.test.tsx`),
validation errors from `zodResolver(schema)` (from `@hookform/resolvers/zod` v5.4.0, paired
with zod v4.4.3 and react-hook-form v7.82 on React 19) were silently dropped: `form.trigger()`
correctly reported the form as invalid (`false`), but `form.formState.errors` remained an empty
object, so no error message ever rendered -- confirmed both in a full page render and in an
isolated `renderHook(() => useForm(...))` test with no resolver-adapter code involved at all
beyond the resolver call itself.

Separately, native HTML5 constraint validation on `<input type="email">` was found to
silently block form submission in both jsdom (test) and real Chromium (verified via the
Playwright smoke test) *before* React's `onSubmit` ever ran, whenever the browser's own
"looks like an email" check failed -- producing inconsistent UX (native browser tooltip
instead of the app's own error styling) and, combined with the resolver bug above, made the
email-validation test fail for two independent reasons simultaneously.

## Decision
1. Removed `@hookform/resolvers` entirely. `lib/validate-form.ts` exports
   `validateWithZod(schema, data, setError)`, which calls `schema.safeParse` directly and
   applies each issue to react-hook-form's own `setError` API. This sidesteps the third-party
   adapter's zod-v4 compatibility bug while keeping zod as the single source of validation
   rules shared by every form.
2. Every `<form>` now sets `noValidate`, so the browser never intercepts submission for its
   own constraint validation -- all validation, and all validation *messaging*, is the app's.

## Consequences
- One extra import (`validateWithZod`) per form instead of a `resolver` option; otherwise the
  same `react-hook-form` API (`register`, `formState.errors`, `handleSubmit`) is used
  unchanged.
- This is a workaround for a specific dependency-version bug, not a permanent architectural
  stance against resolver adapters. Re-evaluate `@hookform/resolvers` compatibility the next
  time either package is upgraded, and this ADR can likely be reverted.
