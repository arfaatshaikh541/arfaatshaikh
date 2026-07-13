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

import LoginPage from "@/app/(auth)/login/page";

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient();
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("LoginPage", () => {
  beforeEach(() => {
    pushMock.mockClear();
    apiFetchMock.mockReset();
  });

  it("shows validation errors for an empty submit without calling the API", async () => {
    const user = userEvent.setup();
    renderWithClient(<LoginPage />);

    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findAllByRole("alert")).not.toHaveLength(0);
    expect(apiFetchMock).not.toHaveBeenCalled();
  });

  it("submits valid credentials and navigates to the dashboard", async () => {
    apiFetchMock.mockResolvedValueOnce({ user: { id: "1" } });
    const user = userEvent.setup();
    renderWithClient(<LoginPage />);

    await user.type(screen.getByLabelText("Email"), "owner@example.com");
    await user.type(screen.getByLabelText("Password"), "hunter22222");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/dashboard"));
    expect(apiFetchMock).toHaveBeenCalledWith(
      "/auth/login",
      expect.objectContaining({ method: "POST" })
    );
  });
});
