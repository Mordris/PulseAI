# The report site

`@pulseai/site` turns an instance's reports into a static site: one page per edition, the latest
edition at the root, an archive, search, an RSS feed, and a sitemap. The design comes from design
tokens, and every visual is generated from report data.

## How a build works

```text
pulse site context      instance config + registries + locales + schemas  ->  .pulse/site-context.json
@pulseai/tokens         engine + instance tokens + config.theme overrides  ->  .pulse/tokens/{tokens.css,light.json,dark.json,fonts.css}
pulse tokens check      contrast and color separation of the resolved tokens
astro build             reports/YYYY/MM/DD/report.json + the files above   ->  dist/
```

The first step is Python, so merging config and registries happens in one place: the site reads
the result and never merges anything itself. `scripts/pulse-site.ts` runs the token step and then
Astro:

```bash
uv run pulse site context --instance <dir>
node packages/site/scripts/pulse-site.ts build --instance <dir>     # also: dev, preview, check
uv run pulse tokens check --instance <dir>
```

In this repository `examples/` is a demo instance with three sample editions:

```bash
pnpm demo:build      # context, tokens, and the site in examples/dist/
pnpm demo:preview    # serve it at http://127.0.0.1:4321/PulseAI/
pnpm demo:dev        # live reload while editing components
pnpm demo:check      # astro check
pnpm demo:e2e        # Playwright, axe, and screenshots in the Playwright container
```

`config.site.url` sets the base path (a GitHub Pages project site serves from `/PulseAI/`). Without
it the site is served from `/` and has no feed or sitemap, because both need absolute links.

## What a page shows

The frame is fixed, so every edition reads the same way:

1. masthead (edition, date, window, headline, Pulse score against the 7-day average)
2. key numbers, TL;DR, and the front page (visuals, usually a dashboard)
3. adoption radar
4. filters
5. the sections, in registry order, with their groups
6. actions, signals, corrections
7. methodology, with the research funnel, source health, and rejected items

Each item is a `<details>` element. Items with `impact` below `deep_dive.min_impact` are briefs
that show their type's `brief_fields`. Deeper items render their type's deep-dive `blocks` in
registry order; a visual whose `block` names one of those blocks renders inside it.

## Themes

Tokens use the [DTCG](https://www.designtokens.org/) format and are layered, lowest precedence
first:

1. `tokens/base/**` and `tokens/base/modes/<mode>.json`
2. `tokens/themes/<preset>/base.json` and `tokens/themes/<preset>/<mode>.json`
3. the same paths under the instance's `tokens/`
4. `config.theme.overrides`: `accent`, `font_display`, `font_body`, and section colors

The engine ships the `pulse`, `paper`, and `terminal` presets. Readers switch between Auto (follow
the OS), Light, and Dark; the choice is remembered, and `?theme=dark` overrides it for one visit.
Charts and diagrams get their colors, fonts, and sizes from the same tokens, so a report never sets
a color.

A new preset is a folder with full `light.json` and `dark.json` themes. Copy an engine preset and
change what differs, then run `pulse tokens check`. The check enforces three things:

- text contrast against every surface a token names in `contrast_against` reaches
  `quality.text_contrast_min`
- section colors, and every declared `distinct` set, stay at least `quality.section_delta_e_min`
  apart
- under each `quality.cvd_simulations` filter, colors stay above `section_cvd_fail` (an error) and
  `section_cvd_target` (a warning)

## Adding an item type

1. Add the detail schema in `schema/item-types/` and the entry in `taxonomy/item-types.yaml`.
2. Add `fields.<name>` labels for its brief fields and `blocks.<id>` labels for its blocks to
   every locale. `pulse registry check` reports any that are missing.
3. Optionally add `packages/site/src/components/items/types/<Component>.astro`, named as the
   registry's `component`. Without it, the type renders through `GenericDetail`: every field as a
   labelled value, plus the visuals placed in its blocks.

## Visuals

| Kind | Rendered by | Without JavaScript |
|---|---|---|
| `vega-lite` | vega-embed, themed from tokens | the chart's data as a table |
| `mermaid` | Mermaid, themed from tokens | the alt text and the diagram source |
| `table` | HTML table | the same |
| `image-ref` | hotlinked `<img>` with caption, credit, and license | the same |
| `dashboard` | CSS grid of stat tiles and visuals | the same, with tables for charts |

A chart or diagram that fails to render keeps its fallback and is marked `data-state="error"`.

## Tests

- `pnpm --filter @pulseai/site test`: Vitest unit tests and component tests through Astro's
  Container API. They need no build and no Python.
- `pnpm demo:e2e`: Playwright against the built demo in `mcr.microsoft.com/playwright`. It covers
  behavior, the no-JavaScript and print views, axe-core audits (no serious or critical
  violations), and screenshots (desktop light, desktop dark, mobile).
- Screenshots live in `packages/site/e2e/__screenshots__/`. After an intended visual change, run
  `pnpm --filter @pulseai/site e2e:visual:update` on a Linux host and review the new images. On
  other systems, download them from the CI run's `playwright-report` artifact.
