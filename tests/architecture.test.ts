import { describe, expect, test } from "bun:test";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const ROOT = resolve(import.meta.dirname, "..");

interface PackageManifest {
  name: string;
  dependencies?: Record<string, string>;
}

function listWorkspaceDirs(parent: "apps" | "packages"): string[] {
  const base = join(ROOT, parent);
  return readdirSync(base)
    .map((entry) => join(base, entry))
    .filter((dir) => statSync(dir).isDirectory());
}

function collectTsFiles(dir: string): string[] {
  const results: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      results.push(...collectTsFiles(full));
    } else if (entry.endsWith(".ts")) {
      results.push(full);
    }
  }
  return results;
}

const IMPORT_PATTERN = /(?:import|export)\s+(?:[^'"]*?\s+from\s+)?["'](@bovie\/[^/'"]+)[^'"]*["']/g;

describe("workspace architecture", () => {
  test("workspace imports follow declared dependencies", () => {
    const appDirs = listWorkspaceDirs("apps");
    const packageDirs = listWorkspaceDirs("packages");
    const projects = new Map<
      string,
      { dir: string; group: "apps" | "packages"; manifest: PackageManifest }
    >();

    for (const dir of appDirs) {
      const manifest = JSON.parse(
        readFileSync(join(dir, "package.json"), "utf8"),
      ) as PackageManifest;
      projects.set(manifest.name, { dir, group: "apps", manifest });
    }
    for (const dir of packageDirs) {
      const manifest = JSON.parse(
        readFileSync(join(dir, "package.json"), "utf8"),
      ) as PackageManifest;
      projects.set(manifest.name, { dir, group: "packages", manifest });
    }

    for (const [name, { dir, manifest }] of projects) {
      const declared = new Set(Object.keys(manifest.dependencies ?? {}));
      for (const file of collectTsFiles(join(dir, "src"))) {
        const content = readFileSync(file, "utf8");
        for (const match of content.matchAll(IMPORT_PATTERN)) {
          const target = match[1];
          if (!target || target === name || !projects.has(target)) {
            continue;
          }
          const targetProject = projects.get(target);
          expect(targetProject?.group).toBe("packages");
          expect(declared.has(target)).toBe(true);
        }
      }
    }
  });

  test("services do not depend on other services", () => {
    const appDirs = listWorkspaceDirs("apps");
    const serviceNames = new Set(
      appDirs.map(
        (dir) =>
          (JSON.parse(readFileSync(join(dir, "package.json"), "utf8")) as PackageManifest).name,
      ),
    );

    for (const dir of [...appDirs, ...listWorkspaceDirs("packages")]) {
      const manifest = JSON.parse(
        readFileSync(join(dir, "package.json"), "utf8"),
      ) as PackageManifest;
      const deps = Object.keys(manifest.dependencies ?? {});
      for (const dep of deps) {
        expect(serviceNames.has(dep)).toBe(false);
      }
    }
  });
});
