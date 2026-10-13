import type { Mode } from "@pulseai/tokens";
import { THEME_DATA_ID, THEME_EVENT } from "../lib/theme.ts";
import type { ThemeData } from "../lib/theme-data.ts";

const DARK_QUERY = "(prefers-color-scheme: dark)";
let cached: ThemeData | undefined;

/** The chart and diagram themes the layout inlined for this page. */
export function themeData(): ThemeData {
  if (cached === undefined) {
    const source = document.getElementById(THEME_DATA_ID)?.textContent;
    if (!source) throw new Error(`#${THEME_DATA_ID} is missing from the page`);
    cached = JSON.parse(source) as ThemeData;
  }
  return cached;
}

/** The modes the tokens define, in token order. */
export function modes(): Mode[] {
  return Object.keys(themeData().vega) as Mode[];
}

/** The mode on screen: the reader's pick, or the OS setting (light or dark) when they follow it. */
export function effectiveMode(): Mode {
  const forced = document.documentElement.dataset.theme;
  if (forced === "light" || forced === "dark") return forced;
  return matchMedia(DARK_QUERY).matches ? "dark" : "light";
}

/** Call back whenever the mode on screen changes (a pick, or an OS change while following it). */
export function onModeChange(callback: (mode: Mode) => void): void {
  window.addEventListener(THEME_EVENT, () => callback(effectiveMode()));
  matchMedia(DARK_QUERY).addEventListener("change", () => {
    if (document.documentElement.dataset.theme === undefined) callback(effectiveMode());
  });
}
