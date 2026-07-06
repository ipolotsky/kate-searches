import "@testing-library/jest-dom/vitest";

// jsdom не реализует matchMedia/ResizeObserver — flowbite-react (useThemeMode, floating-ui)
// на них опирается. Лёгкие полифилы, чтобы компонентные тесты не падали.
if (typeof window !== "undefined") {
  if (window.matchMedia == null) {
    window.matchMedia = (query: string) =>
      ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList;
  }

  if (typeof window.ResizeObserver === "undefined") {
    class ResizeObserverStub {
      observe(): void {}
      unobserve(): void {}
      disconnect(): void {}
    }
    window.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
  }
}
