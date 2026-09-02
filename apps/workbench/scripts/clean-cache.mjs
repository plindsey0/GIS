import {rm} from "node:fs/promises";
import {resolve} from "node:path";

for (const directory of [".next", ".next-dev", ".next-build"]) {
  await rm(resolve(process.cwd(), directory), {recursive: true, force: true});
}
console.log("Removed Workbench-generated Next.js caches.");
