import { describe, expect, test } from "bun:test";
import { scanHash } from "@bovie/collector-store";

// Expected values come from Python: hashlib.sha256(json.dumps(...).encode()).hexdigest().
// Existing checkpoint rows are keyed by these hashes.
describe("scanHash", () => {
  test("escapes non-ASCII and DEL like json.dumps", () => {
    expect(scanHash(["développeur 🚀\x7f", ["CA"], [], 50, 5])).toBe(
      "cba2279089b3b6087fe61590a2f7f6fbbbe5858238822f2a66f4763fcc80d9db",
    );
  });

  test("sorts keys by code point like sort_keys=True", () => {
    expect(
      scanHash(
        ["https://x.wd1.myworkdayjobs.com/wday/cxs/x/C", "é", { b: ["1"], B: ["2"], a: [] }, 40],
        { sortKeys: true },
      ),
    ).toBe("cf8e44f4d191bb576c203256bb35a5474d14b404348a8229d3e5823ca0f3229a");
  });
});
