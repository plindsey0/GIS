import {describe, expect, it} from "vitest";
import {docGroups, docs, docsBySlug} from "./docs";

describe("GIS product documentation catalog", () => {
  it("provides stable unique routes and navigable sections", () => {
    expect(new Set(docs.map((page) => page.slug)).size).toBe(docs.length);
    expect(docsBySlug.get("overview")?.title).toBe("What is GIS?");
    expect(docs.every((page) => page.sections.length > 0 && page.sections.every((section) => section.id && section.title))).toBe(true);
    expect(docGroups).toEqual(expect.arrayContaining(["Start here", "Understand GIS", "Operate GIS", "Trust GIS", "Reference"]));
  });

  it("covers the required operator journeys and trust concepts", () => {
    const text = JSON.stringify(docs).toLowerCase();
    for (const concept of ["market", "collection target", "observation", "signal", "evidence package", "evidence gap", "opportunity", "recommendation", "intervention", "experiment", "outcome", "provenance", "rights", "getting started", "current limitations", "business goal", "deterministic decomposition", "objective dag", "guardrail", "measurement health"]) expect(text).toContain(concept);
    expect(text).toContain("illustrative only");
    expect(text).toContain("human approval");
  });

  it("links operational concepts to live system state", () => {
    const links = docs.flatMap((page) => page.sections.flatMap((section) => section.links?.map((link) => link.href) ?? []));
    expect(links).toEqual(expect.arrayContaining(["/system/sources", "/system/pipelines", "/system/data-flow"]));
  });
});
