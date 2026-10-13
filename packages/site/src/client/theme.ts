import type { Mode } from "@pulseai/tokens";
import { THEME_DATA_ID, THEME_EVENT } from "../lib/theme.ts";
import type { ThemeData } from "../lib/theme-data.ts";

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

/** The modes the tokens define, the default first. */
export function modes(): Mode[] {
  return themeData().modes;
}

function darkQuery(): MediaQueryList {
  return matchMedia(`(prefers-color-scheme: ${themeData().osDark})`);
}

/** The mode on screen: the reader's pick, or the OS setting when they follow it. */
export function effectiveMode(): Mode {
  const { modes: available, osDark } = themeData();
  const forced = document.documentElement.dataset.theme as Mode | undefined;
  if (forced !== undefined && available.includes(forced)) return forced;
  if (available.includes(osDark) && darkQuery().matches) return osDark;
  const [defaultMode] = available;
  if (defaultMode === undefined) throw new Error("the page's theme data names no modes");
  return defaultMode;
}

/** Call back whenever the mode on screen changes (a pick, or an OS change while following it). */
export function onModeChange(callback: (mode: Mode) => void): void {
  window.addEventListener(THEME_EVENT, () => callback(effectiveMode()));
  darkQuery().addEventListener("change", () => {
    if (document.documentElement.dataset.theme === undefined) callback(effectiveMode());
  });
}
