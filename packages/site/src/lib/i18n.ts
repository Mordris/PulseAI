export type Vars = { [name: string]: string | number };

export class MissingStringError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MissingStringError";
  }
}

export interface Translator {
  /** The string for key with {name} placeholders filled; throws when the locale lacks the key. */
  (key: string, vars?: Vars): string;
  /** The string for a key built from data (a field name), or the fallback when there is none. */
  or(key: string, fallback: string, vars?: Vars): string;
  has(key: string): boolean;
  readonly lang: string;
}

/** Fill {name} placeholders; unknown placeholders stay as they are (client code fills them). */
export function interpolate(template: string, vars: Vars = {}): string {
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    Object.hasOwn(vars, name) ? String(vars[name]) : match,
  );
}

export function createTranslator(strings: { [key: string]: string }, lang: string): Translator {
  const translate = (key: string, vars?: Vars): string => {
    const template = strings[key];
    if (template === undefined) {
      throw new MissingStringError(`missing locale string "${key}" for language "${lang}"`);
    }
    return interpolate(template, vars);
  };
  return Object.assign(translate, {
    or: (key: string, fallback: string, vars?: Vars) => interpolate(strings[key] ?? fallback, vars),
    has: (key: string) => Object.hasOwn(strings, key),
    lang,
  });
}

/** "reading_minutes" -> "Reading minutes": the fallback label for a field without a string. */
export function humanize(name: string): string {
  const words = name.replace(/[_-]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
