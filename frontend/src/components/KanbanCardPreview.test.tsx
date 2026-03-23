import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";

describe("KanbanCardPreview", () => {
  it("renders card title and details", () => {
    render(
      <KanbanCardPreview
        card={{ id: "1", title: "Preview title", details: "Preview details" }}
      />
    );

    expect(screen.getByText("Preview title")).toBeInTheDocument();
    expect(screen.getByText("Preview details")).toBeInTheDocument();
  });
});
