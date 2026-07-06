import "@testing-library/jest-dom/vitest";

// If tests using localStorage fail with "localStorage.removeItem is not a
// function", run via `npm test` (not `npx vitest` directly) — recent Node
// versions ship their own experimental global `localStorage` that can
// shadow jsdom's working implementation with a broken stub. The `test`
// script in package.json disables it via NODE_OPTIONS.
