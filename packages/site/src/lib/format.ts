import type { Translator } from "./i18n.ts";

export interface Formatters {
  number(value: number, options?: Intl.NumberFormatOptions): string;
  /** A change with an explicit sign: "+3", "−2", "0". */
  signed(value: number): string;
  /** A calendar date (YYYY-MM-DD) in the long form: "11 October 2026". */
  date(isoDate: string): string;
  /** A calendar date in the short form: "11 Oct". */
  dateShort(isoDate: string): string;
  /** An RFC 3339 timestamp in a time zone: "11 Oct 2026, 17:00". */
  dateTime(timestamp: string, timeZone: string): string;
  /** Values listed with the language's separators: "text, image, audio". */
  list(values: readonly string[]): string;
  /** Any detail or table value as text. */
  value(value: unknown, t: Translator): string;
}

/** Calendar dates are days, not instants: format them in UTC so no time zone shifts the day. */
function day(isoDate: string): Date {
  return new Date(`${isoDate}T00:00:00Z`);
}

export function createFormatters(lang: string): Formatters {
  const numbers = new Intl.NumberFormat(lang);
  const signedNumbers = new Intl.NumberFormat(lang, { signDisplay: "exceptZero" });
  const longDate = new Intl.DateTimeFormat(lang, { dateStyle: "long", timeZone: "UTC" });
  const shortDate = new Intl.DateTimeFormat(lang, {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
  // The narrow conjunction is the language's plain list ("a, b, c"; "a、b、c" in Japanese), as
  // data lists read: authors, modalities, model names.
  const lists = new Intl.ListFormat(lang, { style: "narrow", type: "conjunction" });
  const formatters: Formatters = {
    list: (values) => lists.format(values),
    number: (value, options) =>
      options === undefined
        ? numbers.format(value)
        : new Intl.NumberFormat(lang, options).format(value),
    signed: (value) => signedNumbers.format(value),
    date: (isoDate) => longDate.format(day(isoDate)),
    dateShort: (isoDate) => shortDate.format(day(isoDate)),
    dateTime: (timestamp, timeZone) =>
      new Intl.DateTimeFormat(lang, { dateStyle: "medium", timeStyle: "short", timeZone }).format(
        new Date(timestamp),
      ),
    value: (value, t) => {
      if (value === null || value === undefined || value === "") return t("ui.table.empty_cell");
      if (typeof value === "number") return formatters.number(value);
      if (typeof value === "boolean") return t(value ? "ui.yes" : "ui.no");
      if (Array.isArray(value)) {
        return formatters.list(value.map((entry) => formatters.value(entry, t)));
      }
      if (typeof value === "object") return JSON.stringify(value);
      return String(value);
    },
  };
  return formatters;
}
