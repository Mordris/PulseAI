import type { VisualizationSpec } from "vega-embed";
import { effectiveMode, onModeChange, themeData } from "./theme.ts";

type Spec = { [key: string]: unknown };

/** A Vega-Lite chart that renders over its data table and re-themes with the page. */
class PulseVegaChart extends HTMLElement {
  #spec: Spec | undefined;
  #view: { finalize(): void } | undefined;
  #rendered = false;

  connectedCallback(): void {
    const source = this.querySelector<HTMLScriptElement>("script[type='application/json']");
    try {
      this.#spec = JSON.parse(source?.textContent ?? "") as Spec;
    } catch (error) {
      this.#fail(error);
      return;
    }
    onModeChange(() => void this.render());
    void this.render();
  }

  disconnectedCallback(): void {
    this.#view?.finalize();
  }

  async render(): Promise<void> {
    const canvas = this.querySelector<HTMLElement>("[data-chart]");
    if (canvas === null || this.#spec === undefined) return;
    try {
      const { default: embed } = await import("vega-embed");
      // Charts fill their figure unless the spec sets a width.
      const spec = { width: "container", ...this.#spec } as unknown as VisualizationSpec;
      const result = await embed(canvas, spec, {
        actions: false,
        renderer: "svg",
        config: themeData().vega[effectiveMode()],
        tooltip: { theme: "custom" },
      });
      this.#view?.finalize();
      this.#view = result;
      canvas.hidden = false;
      if (!this.#rendered) {
        // The table stays one click away for readers who want the numbers.
        this.closest("figure")?.querySelector("details[data-chart-table]")?.removeAttribute("open");
        this.#rendered = true;
      }
      this.dataset.state = "rendered";
    } catch (error) {
      this.#fail(error);
    }
  }

  #fail(error: unknown): void {
    this.dataset.state = "error";
    console.error(`chart ${this.closest("figure")?.id ?? ""} failed to render`, error);
  }
}

if (!customElements.get("pulse-vega-chart")) {
  customElements.define("pulse-vega-chart", PulseVegaChart);
}
