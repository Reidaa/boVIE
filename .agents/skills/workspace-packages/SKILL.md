---
name: workspace-packages
description: Use when you add or change a dependency, a test, or a workspace package in BoVIE (package.json, pnpm-workspace.yaml, tsconfig, test/ or tests/).
---

# Workspace packages

- Each package declares every module it imports. Runtime imports in `src/` go in
  `dependencies`. Tools and test-only imports go in `devDependencies`, including
  `typescript` and the `@types/*` its tsconfig names.
- Write third-party versions only in the `catalog:` of `pnpm-workspace.yaml`.
  Packages refer to them as `"catalog:"`. Workspace packages use `"workspace:*"`.
- The root `package.json` holds only workspace-wide tools: Biome, Turbo, Railway,
  and the TypeScript setup for `scripts/` and `.railway/`.
- A test that covers one package goes in that package's `test/` and imports
  `../src/...`. Each such package has `test/tsconfig.json`, a `test` script
  (`bun test`), and a `check` script that also runs `tsc -p test/tsconfig.json`.
- A test that needs several packages, or reads files outside one package, goes in
  `tests/` (`@bovie/integration-tests`).
- Shared test helpers go in `packages/test-support`. It must not depend on a
  package that uses it, or Turbo reports a cycle. For example, pass a store's
  `upgrade` to `createTestDbContext().create(upgrade)`.
