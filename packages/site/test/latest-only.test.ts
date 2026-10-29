import { describe, expect, it } from "vitest";
import { latestOnly } from "../src/lib/latest-only.ts";

const tick = () => new Promise<void>((resolve) => setTimeout(resolve, 5));

describe("latestOnly", () => {
  it("skips calls a newer call replaced before they started", async () => {
    const runs: string[] = [];
    let mode = "light";
    const draw = latestOnly(async () => {
      const drawn = mode;
      await tick();
      runs.push(drawn);
    });
    void draw();
    mode = "dark";
    void draw();
    mode = "light";
    await draw();
    expect(runs).toEqual(["light"]);
  });

  it("lets a running call finish before the next one starts", async () => {
    const events: string[] = [];
    let mode = "light";
    const draw = latestOnly(async () => {
      const drawn = mode;
      events.push(`start ${drawn}`);
      await tick();
      events.push(`end ${drawn}`);
    });
    const first = draw();
    await tick().then(() => undefined);
    mode = "dark";
    await draw();
    await first;
    expect(events).toEqual(["start light", "end light", "start dark", "end dark"]);
  });

  it("keeps going after a call fails", async () => {
    let calls = 0;
    const draw = latestOnly(async () => {
      calls += 1;
      if (calls === 1) throw new Error("broken");
    });
    await draw().catch(() => undefined);
    await draw();
    expect(calls).toBe(2);
  });
});
