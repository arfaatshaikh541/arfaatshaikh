import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn() }),
}));

const apiFetchMock = vi.fn();
vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  };
});

import SignupPage from "@/app/(auth)/signup/page";

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient();
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("SignupPage", () => {
  beforeEach(() => {
    pushMock.mockClear();
    apiFetchMock.mockReset();
  });

  it("shows validation errors for an empty submit without calling the API", async () => {
    const user = userEvent.setup();
    renderWithClient(<SignupPage />);

    await user.click(screen.getByRole("button", { name: "Create workspace" }));

    expect(await screen.findAllByRole("alert")).not.toHaveLength(0);
    expect(apiFetchMock).not.toHaveBeenCalled();
  });

  it("auto-derives the workspace slug from the company name", async () => {
    const user = userEvent.setup();
    renderWithClient(<SignupPage />);

    await user.type(screen.getByLabelText("Company name"), "Acme Consulting Co");

    expect(screen.getByLabelText("Workspace URL")).toHaveValue("acme-consulting-co");
  });

  it("submits a valid signup and navigates to onboarding", async () => {
    apiFetchMock.mockResolvedValueOnce({ user: { id: "1" } });
    const user = userEvent.setup();
    renderWithClient(<SignupPage />);

    await user.type(screen.getByLabelText("Company name"), "Acme Consulting");
    await user.type(screen.getByLabelText("First name"), "Jane");
    await user.type(screen.getByLabelText("Last name"), "Doe");
    await user.type(screen.getByLabelText("Work email"), "jane@acme.example");
    await user.type(screen.getByLabelText("Password"), "SignupPassw0rd!123");
    await user.type(screen.getByLabelText("Confirm password"), "SignupPassw0rd!123");
    await user.click(screen.getByRole("button", { name: "Create workspace" }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/onboarding"));
    expect(apiFetchMock).toHaveBeenCalledWith(
      "/auth/signup",
      expect.objectContaining({ method: "POST", withTenant: false })
    );
  });

  it("shows a friendly message when the slug is already taken", async () => {
    const { ApiError } = await import("@/lib/api-client");
    apiFetchMock.mockRejectedValueOnce(new ApiError(409, "Tenant slug already in use."));
    const user = userEvent.setup();
    renderWithClient(<SignupPage />);

    await user.type(screen.getByLabelText("Company name"), "Acme Consulting");
    await user.type(screen.getByLabelText("First name"), "Jane");
    await user.type(screen.getByLabelText("Last name"), "Doe");
    await user.type(screen.getByLabelText("Work email"), "jane@acme.example");
    await user.type(screen.getByLabelText("Password"), "SignupPassw0rd!123");
    await user.type(screen.getByLabelText("Confirm password"), "SignupPassw0rd!123");
    await user.click(screen.getByRole("button", { name: "Create workspace" }));

    expect(await screen.findByText(/already taken/i)).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });
});
