import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RootLayout from "@/app/layout";

describe("RootLayout", () => {
  it("renders children", () => {
    render(
      <RootLayout>
        <div>Child content</div>
      </RootLayout>
    );

    expect(screen.getByText("Child content")).toBeInTheDocument();
  });
});
