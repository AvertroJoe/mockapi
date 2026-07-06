import "@testing-library/jest-dom/vitest";

// If tests using localStorage fail with "localStorage.removeItem is not a
// function", you're likely on a Node version newer than the ones this
// project targets (see "engines" in package.json — ^20 || ^22). Some
// very new Node builds ship their own experimental global `localStorage`
// that can shadow jsdom's working implementation with a broken stub.
// `NODE_OPTIONS=--no-experimental-webstorage vitest run` works around it
// on Node versions that recognize that flag, but it's not something to
// bake into the committed npm script — older/stable Node (including
// what CI runs) doesn't recognize the flag at all and exits immediately
// if it's set. Easiest real fix: use Node 20 or 22 for this project.
