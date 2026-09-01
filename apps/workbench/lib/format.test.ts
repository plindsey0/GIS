import {describe, expect, it} from "vitest";
import {formatDate, formatNumber, humanize} from "./format";

describe("operator formatting", () => {
  it("does not render count decimals", () => expect(formatNumber("596.000000")).toBe("596"));
  it("preserves meaningful decimals and percentages", () => {
    expect(formatNumber("1.720000", "decimal")).toBe("1.72");
    expect(formatNumber("0.034", "percent")).toBe("3.4%");
  });
  it("localizes timestamps and humanizes status values", () => {
    expect(formatDate("2026-09-01T09:45:41.545958Z")).toContain("Sep 1, 2026");
    expect(humanize("INSUFFICIENT_HISTORY")).toBe("Insufficient history");
  });
});
