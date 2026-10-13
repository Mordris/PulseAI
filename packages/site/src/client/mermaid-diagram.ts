import { effectiveMode, onModeChange, themeData } from "./theme.ts";

let sequence = 0;

/** A Mermaid diagram that renders over its alt text and re-themes with the page. */
class PulseMermaid extends HTMLElement {
  connectedCallback(): void {
    onModeChange(() => void this.render());
    void this.render();
  }

  async render(): Promise<void> {
    const canvas = this.querySelector<HTMLElement>("[data-diagram]");
    const code = this.closest("figure")?.querySelector("[data-diagram-source] code")?.textContent;
    if (canvas === null || !code) return;
    try {
      const [{ default: mermaid }, { default: DOMPurify }] = await Promise.all([
        import("mermaid"),
        import("dompurify"),
      ]);
      const variables = themeData().mermaid[effectiveMode()];
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        // A broken diagram keeps its alt text and source; Mermaid's own error graphic stays out.
        suppressErrorRendering: true,
        theme: "base",
        themeVariables: variables,
        fontFamily: variables.fontFamily,
      });
      sequence += 1;
      const { svg } = await mermaid.render(`pulse-mermaid-${sequence}`, code);
      // Mermaid already sanitizes under securityLevel "strict"; sanitize again here, with the
      // settings Mermaid uses, so nothing reaches the page unsanitized whatever Mermaid does.
      canvas.innerHTML = DOMPurify.sanitize(svg, {
        ADD_TAGS: ["foreignobject"],
        ADD_ATTR: ["dominant-baseline"],
        HTML_INTEGRATION_POINTS: { foreignobject: true },
      });
      canvas.hidden = false;
      this.querySelector<HTMLElement>("[data-diagram-fallback]")?.setAttribute("hidden", "");
      this.dataset.state = "rendered";
    } catch (error) {
      this.dataset.state = "error";
      console.error(`diagram ${this.closest("figure")?.id ?? ""} failed to render`, error);
    }
  }
}

if (!customElements.get("pulse-mermaid")) {
  customElements.define("pulse-mermaid", PulseMermaid);
}
