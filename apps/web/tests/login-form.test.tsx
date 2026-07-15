import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
}));

const postMock = vi.fn();
vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return {
    ...actual,
    apiClient: {
      ...actual.apiClient,
      post: (...args: unknown[]) => postMock(...args),
      get: vi.fn().mockRejectedValue(new actual.ApiError(401, "authentication_required", "nope", {})),
    },
  };
});

// eslint-disable-next-line import/first
import LoginPage from "@/app/(auth)/login/page";

function renderWithProviders(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("LoginPage", () => {
  beforeEach(() => {
    postMock.mockReset();
    replace.mockReset();
  });

  it("shows a validation error for an invalid email and does not call the API", async () => {
    renderWithProviders(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "not-an-email" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "something" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(postMock).not.toHaveBeenCalled();
  });

  it("requires a password", async () => {
    renderWithProviders(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "owner@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Enter your password.")).toBeInTheDocument();
    expect(postMock).not.toHaveBeenCalled();
  });

  it("submits valid credentials and redirects to the dashboard", async () => {
    postMock.mockResolvedValue({
      user: { id: "1", email: "owner@example.com", full_name: "Owner", email_verified: true, mfa_enabled: false },
      memberships: [
        {
          membership_id: "m1",
          tenant_id: "t1",
          tenant_name: "Acme",
          tenant_slug: "acme",
          tenant_status: "active",
          role_name: "tenant_owner",
        },
      ],
      active_membership_id: "m1",
      csrf_token: "csrf",
    });

    renderWithProviders(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "owner@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(postMock).toHaveBeenCalledWith("/api/auth/login", {
      email: "owner@example.com",
      password: "correct-password",
    }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
  });
});
