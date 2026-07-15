import { TextInput } from "@gridkeep/ui";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("TextInput", () => {
  it("associates its label with the input for accessible naming", () => {
    render(<TextInput label="Email address" />);
    const input = screen.getByLabelText("Email address");
    expect(input).toBeInTheDocument();
  });

  it("marks the input invalid and links the error message when an error is present", () => {
    render(<TextInput label="Password" error="Password is required." />);
    const input = screen.getByLabelText("Password");
    expect(input).toHaveAttribute("aria-invalid", "true");

    const error = screen.getByRole("alert");
    expect(error).toHaveTextContent("Password is required.");
    expect(input.getAttribute("aria-describedby")).toContain(error.id);
  });

  it("renders a hint without marking the field invalid", () => {
    render(<TextInput label="Password" hint="At least 12 characters." />);
    const input = screen.getByLabelText("Password");
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(screen.getByText("At least 12 characters.")).toBeInTheDocument();
  });
});
