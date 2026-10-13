import {
  type Filters,
  type ItemFacets,
  isFiltering,
  matchesFilters,
  NO_FILTERS,
} from "../lib/filters.ts";

const ITEM = "details[data-item]";

function facets(item: HTMLElement): ItemFacets {
  const { section = "", type = "", impact = "0", confidence = "", update = "false" } = item.dataset;
  return { section, type, impact: Number(impact), confidence, update: update === "true" };
}

function value(form: HTMLFormElement, name: string, fallback: string): string {
  const field = form.elements.namedItem(name);
  return field instanceof HTMLSelectElement ? field.value : fallback;
}

/** The id a URL fragment names; a malformed escape (a hand-edited link) is taken as written. */
function fragmentId(hash: string): string {
  const raw = hash.slice(1);
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}

/** Open the item a URL fragment names (and the details around it), then scroll to it. */
function openTarget(hash: string): void {
  if (hash.length < 2) return;
  const target = document.getElementById(fragmentId(hash));
  if (target === null) return;
  for (let node: HTMLElement | null = target; node !== null; node = node.parentElement) {
    if (node instanceof HTMLDetailsElement) node.open = true;
  }
  target.scrollIntoView();
}

/** Filters, expand/collapse all, permalinks, and print expansion for a report page. */
class PulseReportControls extends HTMLElement {
  #printOpen = new Set<HTMLDetailsElement>();

  connectedCallback(): void {
    const form = this.querySelector("form");
    if (form === null) return;
    form.addEventListener("change", () => this.#apply(form));
    // The reset event fires before the controls change; apply the filters once they have.
    form.addEventListener("reset", () => setTimeout(() => this.#apply(form)));
    form.addEventListener("submit", (event) => event.preventDefault());
    this.querySelector("[data-expand-all]")?.addEventListener("click", () => this.#toggleAll(true));
    this.querySelector("[data-collapse-all]")?.addEventListener("click", () =>
      this.#toggleAll(false),
    );
    window.addEventListener("hashchange", () => openTarget(location.hash));
    window.addEventListener("beforeprint", () => this.#beforePrint());
    window.addEventListener("afterprint", () => this.#afterPrint());
    openTarget(location.hash);
    this.hidden = false;
    this.#apply(form);
  }

  #items(): HTMLDetailsElement[] {
    return [...document.querySelectorAll<HTMLDetailsElement>(ITEM)];
  }

  #apply(form: HTMLFormElement): void {
    const filters: Filters = {
      section: value(form, "section", NO_FILTERS.section),
      type: value(form, "type", NO_FILTERS.type),
      minImpact: Number(value(form, "min_impact", String(NO_FILTERS.minImpact))),
      confidence: value(form, "confidence", NO_FILTERS.confidence),
      status: value(form, "status", NO_FILTERS.status),
    };
    const items = this.#items();
    let shown = 0;
    for (const item of items) {
      const visible = matchesFilters(facets(item), filters);
      item.hidden = !visible;
      if (visible) shown += 1;
    }
    // While a filter is set, a group or section with no matching item disappears with its
    // heading; with no filter set, everything shows, notes-only sections included.
    const filtering = isFiltering(filters);
    for (const container of document.querySelectorAll<HTMLElement>("[data-filter-group]")) {
      container.hidden = filtering && container.querySelector(`${ITEM}:not([hidden])`) === null;
    }
    const status = this.querySelector<HTMLElement>("[data-filter-status]");
    if (status !== null) {
      const template = shown === 0 ? status.dataset.emptyTemplate : status.dataset.countTemplate;
      status.textContent = (template ?? "")
        .replace("{shown}", String(shown))
        .replace("{total}", String(items.length));
    }
  }

  #toggleAll(open: boolean): void {
    for (const item of this.#items()) {
      if (!item.hidden) item.open = open;
    }
  }

  #beforePrint(): void {
    for (const item of document.querySelectorAll<HTMLDetailsElement>("details")) {
      if (!item.open) {
        this.#printOpen.add(item);
        item.open = true;
      }
    }
  }

  #afterPrint(): void {
    for (const item of this.#printOpen) item.open = false;
    this.#printOpen.clear();
  }
}

if (!customElements.get("pulse-report-controls")) {
  customElements.define("pulse-report-controls", PulseReportControls);
}
