import { THEME_EVENT, THEME_STORAGE_KEY } from "../lib/theme.ts";
import { modes } from "./theme.ts";

/** Apply a theme choice: a mode forces it; any other choice (auto) follows the OS. */
export function chooseTheme(choice: string): void {
  const root = document.documentElement;
  root.dataset.themeChoice = choice;
  if ((modes() as string[]).includes(choice)) {
    root.dataset.theme = choice;
  } else {
    delete root.dataset.theme;
  }
  try {
    localStorage.setItem(THEME_STORAGE_KEY, choice);
  } catch {
    // Storage is blocked: the choice still applies to this page.
  }
  window.dispatchEvent(new CustomEvent(THEME_EVENT));
}

class PulseThemeSwitch extends HTMLElement {
  connectedCallback(): void {
    const current = document.documentElement.dataset.themeChoice;
    for (const input of this.querySelectorAll<HTMLInputElement>("input[type=radio]")) {
      input.checked = input.value === current;
      input.addEventListener("change", () => {
        if (input.checked) chooseTheme(input.value);
      });
    }
    this.hidden = false;
  }
}

if (!customElements.get("pulse-theme-switch")) {
  customElements.define("pulse-theme-switch", PulseThemeSwitch);
}
