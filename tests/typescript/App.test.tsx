/**
 * @vitest-environment jsdom
 *
 * End-to-end tests for the main App component.
 * Tests the overall application layout: toolbar, sidebar, editor, panel, status bar.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// ---------------------------------------------------------------------------
// Mock Zustand store
// ---------------------------------------------------------------------------

const mockStore = {
  sidebarVisible: true,
  panelVisible: true,
  onboardingComplete: true,
  toasts: [],
  toggleSidebar: vi.fn(),
  togglePanel: vi.fn(),
};

vi.mock("../src/renderer/stores/useAppStore", () => ({
  __esModule: true,
  default: (selector?: (s: typeof mockStore) => unknown) => {
    if (selector) return selector(mockStore);
    return mockStore;
  },
}));

// ---------------------------------------------------------------------------
// Mock child components
// ---------------------------------------------------------------------------

vi.mock("../src/renderer/components/Sidebar", () => ({
  __esModule: true,
  default: () => <div data-testid="sidebar">Sidebar Content</div>,
}));

vi.mock("../src/renderer/components/StatusBar", () => ({
  __esModule: true,
  default: () => <div data-testid="status-bar">Status Bar</div>,
}));

vi.mock("../src/renderer/components/Panel", () => ({
  __esModule: true,
  default: () => <div data-testid="panel">Panel Content</div>,
}));

vi.mock("../src/renderer/components/Editor", () => ({
  __esModule: true,
  default: () => <div data-testid="editor">Editor Content</div>,
}));

vi.mock("../src/renderer/components/OnboardingModal", () => ({
  __esModule: true,
  default: () => <div data-testid="onboarding">Onboarding Modal</div>,
}));

vi.mock("../src/renderer/components/ToastContainer", () => ({
  __esModule: true,
  default: () => <div data-testid="toast-container">Toasts</div>,
}));

vi.mock("../src/renderer/components/premium/AnimatedBackground", () => ({
  __esModule: true,
  AnimatedBackground: () => <div data-testid="animated-bg">Animated BG</div>,
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => (
      <div {...props}>{children}</div>
    ),
    aside: ({ children, ...props }: any) => (
      <aside {...props}>{children}</aside>
    ),
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// ---------------------------------------------------------------------------
// Mock react-router-dom
// ---------------------------------------------------------------------------

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useLocation: () => ({ pathname: "/" }),
    MemoryRouter: ({ children }: any) => <>{children}</>,
  };
});

// ---------------------------------------------------------------------------
// Import App after mocks
// ---------------------------------------------------------------------------

import App from "../src/renderer/App";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("App", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStore.sidebarVisible = true;
    mockStore.panelVisible = true;
    mockStore.onboardingComplete = true;
  });

  it("renders without crashing", () => {
    const { container } = render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(container).toBeTruthy();
  });

  it("renders the toolbar with app name", () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByText("Construct")).toBeDefined();
  });

  it("renders the toolbar with version", () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByText("v0.1.0")).toBeDefined();
  });

  it("renders sidebar by default", () => {
    mockStore.sidebarVisible = true;
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByTestId("sidebar")).toBeDefined();
  });

  it("hides sidebar when sidebarVisible is false", () => {
    mockStore.sidebarVisible = false;
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.queryByTestId("sidebar")).toBeNull();
  });

  it("renders editor area", () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByTestId("editor")).toBeDefined();
  });

  it("renders panel by default", () => {
    mockStore.panelVisible = true;
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByTestId("panel")).toBeDefined();
  });

  it("hides panel when panelVisible is false", () => {
    mockStore.panelVisible = false;
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.queryByTestId("panel")).toBeNull();
  });

  it("renders status bar", () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByTestId("status-bar")).toBeDefined();
  });

  it("renders toast container", () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByTestId("toast-container")).toBeDefined();
  });

  it("renders animated background", () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByTestId("animated-bg")).toBeDefined();
  });

  it("shows onboarding modal when not complete", () => {
    mockStore.onboardingComplete = false;
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByTestId("onboarding")).toBeDefined();
  });

  it("hides onboarding modal when complete", () => {
    mockStore.onboardingComplete = true;
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.queryByTestId("onboarding")).toBeNull();
  });

  it("renders main layout container", () => {
    const { container } = render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    const mainLayout = container.querySelector(".flex-1.min-h-0.overflow-hidden");
    expect(mainLayout).toBeTruthy();
  });

  it("has correct flex layout structure", () => {
    const { container } = render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    // Root should be a flex column
    const root = container.firstElementChild;
    expect(root?.classList.contains("flex")).toBe(true);
    expect(root?.classList.contains("flex-col")).toBe(true);
  });
});
