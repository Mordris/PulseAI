# ADR 0002: How the report site renders

- Status: accepted
- Date: 2026-10-12

## Context

Reports are JSON documents written by agents. The site has to look the same every day and work
without JavaScript, in print, in both themes, and on phones. It must also let an instance restyle
or extend it without code, and never copy third-party content it may not redistribute.

## Decision

- **Merging stays in Python.** `pulse site context` writes one validated file holding the
  effective config, merged registries, locale strings, and schemas. The site reads that file and
  never merges anything itself.
- **Tokens drive every design value.** DTCG files are layered (engine, preset, instance, config
  overrides) and resolved with Style Dictionary. CSS custom properties and per-mode maps theme the
  page, the charts, and the diagrams.
- **Enum values get their colors from tokens.** Confidence, severity, ring, and changelog-tag
  colors are tokens (`color.<enum>.<value>`), so a new enum value fails the build until a token
  exists.
- **Islands are custom elements.** Charts (vega-embed) and diagrams (Mermaid) render on the client
  over a server-rendered fallback: a data table or alt text plus source. There is no UI framework,
  and every page is complete without JavaScript.
- **Mermaid renders on the client.** `astro-mermaid` transforms Markdown code fences, and reports
  are JSON.
- **Images are hotlinked.** They are `<img>` elements, not Astro `<Image>`, and Astro's sharp
  optimizer is not installed. Optimizing would copy third-party images, and their licenses may
  not allow copies.
- **The engine packages find their data through their package names.** They use
  `require.resolve("<package>/package.json")`, so the paths stay right after Vite bundles them into
  the server build.

## Consequences

- An instance restyles the site with token files and config, and adds an item type with a schema,
  registry entries, and locale strings. A component is optional.
- Every color, contrast ratio, and color-vision-deficiency separation can be checked before
  publishing (`pulse tokens check`).
- Without JavaScript, charts appear as tables and diagrams as alt text plus source. Both are
  readable, but plainer.
- Remote images can disappear. Their captions, credits, and alt text keep the item readable.
