/** Names shared by the server-rendered frame and the client scripts. */
export const THEME_STORAGE_KEY = "pulse-theme";
export const THEME_DATA_ID = "pulse-theme-data";
export const THEME_EVENT = "pulse:theme";

/** JSON safe to put inside a <script> element: "<" and line separators are escaped. */
export function jsonForScript(value: unknown): string {
  return JSON.stringify(value)
    .replaceAll("<", "\\u003c")
    .replaceAll(" ", "\\u2028")
    .replaceAll(" ", "\\u2029");
}
