import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StatusBar from "./StatusBar";

// Mock the zustand store
const toggleSidebarMock = vi.fn();
const togglePanelMock = vi.fn();

vi.mock("@/stores/useAppStore", () => ({
  default: (selector: (state: unknown) => unknown) => {
    const state = {
      sidebarVisible: true,
      panelVisible: true,
      toggleSidebar: toggleSidebarMock,
      togglePanel: togglePanelMock,
      cursorPosition: { line: 5, column: 12 },
    };
    return selector(state);
  },
}));

describe("StatusBar", () => {
  it("renders without crashing", () => {
    render(<StatusBar />);
    expect(screen.getByText("construct v0.1.0-alpha")).toBeInTheDocument();
  });

  it("displays the correct version text", () => {
    render(<StatusBar />);
    expect(screen.getByText("construct v0.1.0-alpha")).toBeInTheDocument();
  });

  it("displays the git branch name", () => {
    render(<StatusBar />);
    expect(screen.getByText("main")).toBeInTheDocument();
  });

  it("displays agent status as idle", () => {
    render(<StatusBar />);
    expect(screen.getByText("agent:idle")).toBeInTheDocument();
  });

  it("displays memory usage", () => {
    render(<StatusBar />);
    expect(screen.getByText(/mem:34%/)).toBeInTheDocument();
  });

  it("displays context usage", () => {
    render(<StatusBar />);
    expect(screen.getByText(/ctx:12k\/200k/)).toBeInTheDocument();
  });

  it("displays cursor position", () => {
    render(<StatusBar />);
    expect(screen.getByText(/ln 5, col 12/)).toBeInTheDocument();
  });

  it("displays encoding info", () => {
    render(<StatusBar />);
    expect(screen.getByText("utf-8")).toBeInTheDocument();
  });

  it("displays language info", () => {
    render(<StatusBar />);
    expect(screen.getByText("typescript")).toBeInTheDocument();
  });

  it("calls toggleSidebar when sidebar button is clicked", async () => {
    const user = userEvent.setup();
    render(<StatusBar />);

    const sidebarButton = screen.getByTitle("Toggle Sidebar");
    await user.click(sidebarButton);

    expect(toggleSidebarMock).toHaveBeenCalledTimes(1);
  });

  it("calls togglePanel when panel button is clicked", async () => {
    const user = userEvent.setup();
    render(<StatusBar />);

    const panelButton = screen.getByTitle("Toggle Panel");
    await user.click(panelButton);

    expect(togglePanelMock).toHaveBeenCalledTimes(1);
  });

  it("renders footer element", () => {
    render(<StatusBar />);
    const footer = screen.getByRole("contentinfo");
    expect(footer).toBeInTheDocument();
  });
});
