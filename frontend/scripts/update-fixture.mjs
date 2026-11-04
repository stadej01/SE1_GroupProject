import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
// Only overwrite the fixture after successful validation.
const result = execFileSync(process.env.PYTHON ?? "python", ["-m", "dialogue_graph", "../fixtures/merchant.md"], {
  cwd: new URL("../../backend/", import.meta.url), encoding: "utf8",
});
writeFileSync(new URL("../../fixtures/merchant.graph.json", import.meta.url), result);
