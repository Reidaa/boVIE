package tests

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strings"
	"testing"
)

const modulePrefix = "github.com/Reidaa/boVIE/"

type goPackage struct {
	ImportPath string   `json:"ImportPath"`
	Imports    []string `json:"Imports"`
	Deps       []string `json:"Deps"`
}

func repoRoot(t *testing.T) string {
	t.Helper()
	wd, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	return filepath.Dir(wd)
}

func listPackages(t *testing.T, root string) []goPackage {
	t.Helper()
	cmd := exec.Command("go", "list", "-json", "./apps/...", "./packages/...")
	cmd.Dir = root
	out, err := cmd.Output()
	if err != nil {
		t.Fatalf("go list: %v", err)
	}
	dec := json.NewDecoder(strings.NewReader(string(out)))
	var pkgs []goPackage
	for dec.More() {
		var p goPackage
		if err := dec.Decode(&p); err != nil {
			t.Fatalf("decode go list output: %v", err)
		}
		pkgs = append(pkgs, p)
	}
	return pkgs
}

func serviceName(importPath string) (string, bool) {
	rel, ok := strings.CutPrefix(importPath, modulePrefix+"apps/")
	if !ok {
		return "", false
	}
	name, _, _ := strings.Cut(rel, "/")
	return name, true
}

func TestLibrariesNeverImportServicesAndServicesStayIsolated(t *testing.T) {
	root := repoRoot(t)
	pkgs := listPackages(t, root)
	if len(pkgs) == 0 {
		t.Fatal("no packages found")
	}

	for _, pkg := range pkgs {
		if strings.HasPrefix(pkg.ImportPath, modulePrefix+"packages/") {
			for _, dep := range pkg.Deps {
				if svc, isSvc := serviceName(dep); isSvc {
					t.Errorf("library %s transitively imports service %s (%s)", pkg.ImportPath, svc, dep)
				}
			}
		}
		if ownSvc, isSvc := serviceName(pkg.ImportPath); isSvc {
			for _, dep := range pkg.Deps {
				if otherSvc, otherIsSvc := serviceName(dep); otherIsSvc && otherSvc != ownSvc {
					t.Errorf("service %s (%s) imports another service %s (%s)", ownSvc, pkg.ImportPath, otherSvc, dep)
				}
			}
		}
	}
}

func TestServiceForbiddenDependenciesAndBinaries(t *testing.T) {
	root := repoRoot(t)
	pkgs := listPackages(t, root)
	depsByPath := make(map[string][]string, len(pkgs))
	for _, p := range pkgs {
		depsByPath[p.ImportPath] = p.Deps
	}

	services := []struct {
		name      string
		pkg       string
		forbidden []string
	}{
		{
			name: "collector-business-france",
			pkg:  "./apps/collector-business-france",
			forbidden: []string{
				modulePrefix + "packages/discordstore",
			},
		},
		{
			name: "collector-wttj",
			pkg:  "./apps/collector-wttj",
			forbidden: []string{
				modulePrefix + "packages/discordstore",
				modulePrefix + "apps/collector-business-france",
			},
		},
		{
			name: "collector-workday",
			pkg:  "./apps/collector-workday",
			forbidden: []string{
				modulePrefix + "packages/discordstore",
			},
		},
		{
			name: "discord-intake",
			pkg:  "./apps/discord-intake",
			forbidden: []string{
				modulePrefix + "packages/collectorstore",
			},
		},
		{
			name: "discord-sender",
			pkg:  "./apps/discord-sender",
			forbidden: []string{
				modulePrefix + "packages/collectorstore",
				modulePrefix + "packages/natsclient",
				"github.com/nats-io/nats.go",
			},
		},
	}

	// Filter out DB/webhook env vars so --help and --version prove zero side effects on startup.
	cleanEnv := make([]string, 0, len(os.Environ()))
	for _, entry := range os.Environ() {
		if strings.HasPrefix(entry, "DATABASE_URL=") || strings.HasPrefix(entry, "DISCORD_WEBHOOK_URL=") {
			continue
		}
		cleanEnv = append(cleanEnv, entry)
	}

	binDir := t.TempDir()
	for _, svc := range services {
		t.Run(svc.name, func(t *testing.T) {
			importPath := modulePrefix + strings.TrimPrefix(svc.pkg, "./")
			deps := depsByPath[importPath]
			for _, blocked := range svc.forbidden {
				if slices.Contains(deps, blocked) {
					t.Errorf("service %s unexpectedly depends on %s", svc.name, blocked)
				}
			}

			bin := filepath.Join(binDir, svc.name)
			build := exec.Command("go", "build", "-o", bin, svc.pkg)
			build.Dir = root
			if out, err := build.CombinedOutput(); err != nil {
				t.Fatalf("build %s: %v\n%s", svc.name, err, out)
			}

			help := exec.Command(bin, "--help")
			help.Dir = binDir
			help.Env = cleanEnv
			if out, err := help.CombinedOutput(); err != nil {
				t.Fatalf("%s --help failed: %v\n%s", svc.name, err, out)
			}

			if svc.name == "collector-business-france" {
				ver := exec.Command(bin, "--version")
				ver.Dir = binDir
				ver.Env = cleanEnv
				out, err := ver.CombinedOutput()
				if err != nil {
					t.Fatalf("%s --version failed: %v\n%s", svc.name, err, out)
				}
				if !strings.HasPrefix(strings.TrimSpace(string(out)), "Bovie ") {
					t.Fatalf("unexpected --version output: %q", string(out))
				}
			}
		})
	}

	// Verify both migration binaries also build and answer --help without DATABASE_URL.
	for _, mig := range []struct {
		name string
		pkg  string
	}{
		{"collector-store-migrate", "./packages/collectorstore/cmd/collector-store-migrate"},
		{"discord-store-migrate", "./packages/discordstore/cmd/discord-store-migrate"},
	} {
		t.Run(mig.name, func(t *testing.T) {
			bin := filepath.Join(binDir, mig.name)
			build := exec.Command("go", "build", "-o", bin, mig.pkg)
			build.Dir = root
			if out, err := build.CombinedOutput(); err != nil {
				t.Fatalf("build %s: %v\n%s", mig.name, err, out)
			}
			help := exec.Command(bin, "--help")
			help.Dir = binDir
			help.Env = cleanEnv
			if out, err := help.CombinedOutput(); err != nil {
				t.Fatalf("%s --help failed: %v\n%s", mig.name, err, out)
			}
		})
	}
}
