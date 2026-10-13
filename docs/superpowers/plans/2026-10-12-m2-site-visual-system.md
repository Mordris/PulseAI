# M2 Site & Visual System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a validated `report.json` into a fast, accessible, heavily visualized static site. The site has a fixed frame, per-type deep-dives, generative charts, diagrams and dashboards, a token-driven theme system with an Auto/Light/Dark switch, search, and automated design, accessibility and visual-regression gates.

**Architecture:**
- The Python CLI (`pulse site context`) resolves everything an instance can override into one validated JSON file, so merge logic stays single-sourced in Python. That covers the effective config, the merged sections and item-type registries, locale strings with fallbacks, and the schemas reports are checked against.
- A Node package (`@pulseai/tokens`) layers DTCG design tokens (engine → preset → instance → config overrides) and resolves them with Style Dictionary into CSS custom properties and per-mode token maps. `pulse tokens check` (ColorAide) gates the maps on contrast, ΔE and colour-blindness rules.
- The Astro site (`@pulseai/site`) loads reports through a validating content loader and renders a fixed frame from registry order. Visuals are progressive-enhancement islands (vega-embed, Mermaid) written as custom elements, so every page reads without JavaScript.
- Playwright drives E2E, axe-core and screenshot tests inside the pinned Playwright container.

**Tech Stack:**
- **Site:** Astro 7.3.8 (static, content layer, Container API), TypeScript 6.0.3 in the site package (the `@astrojs/check` peer range; the rest of the repo stays on 7.0.2), Zod 4.6.
- **Tokens:** Style Dictionary 5.6.1 (DTCG).
- **Visuals:** Vega 6.4.0, Vega-Lite 6.5.0, vega-embed 7.3.0, Mermaid 12.1.0.
- **Search and feeds:** Pagefind 1.5.2 + astro-pagefind 2.0.1, @astrojs/rss 4.0.19, @astrojs/sitemap 3.7.4.
- **Fonts:** Fontsource variable fonts (Inter, Newsreader, Source Serif 4, JetBrains Mono, all 5.3.x).
- **Contracts:** json-schema-to-typescript 16.0.0.
- **Testing:** Playwright 1.64.0 (image `mcr.microsoft.com/playwright:v1.64.0-noble`), @axe-core/playwright 4.13.0 (axe-core 4.14.0), Vitest 5.0.4.
- **Python:** ColorAide 8.13.

**Verification:** every code block below was run before this plan was written. The run used a scratch copy of the repository at `281fe32`, applying the tasks in order.
- **Python:** 397 tests, Ruff and Pyright pass.
- **TypeScript:** 51 contracts tests, 13 tokens tests and 67 site tests pass, along with Biome, `tsc` and `astro check`.
- **Token gate:** the three presets and the demo pass `pulse tokens check`.
- **Browser:** 78 Playwright tests pass in the container (22 functional and 4 screenshot tests in each of 3 projects).
- **Config:** zizmor and the Renovate validator report no problems.

An executor who finds a difference has found a real change (a new upstream release, say) and should fix the code, not the expected values.

**Spec:** `docs/superpowers/specs/2026-10-11-pulseai-daily-research-routine-design.md` (v2). Read §3 (engineering standards), §9 (report data model), §12 (site, template and visual system), §15 (failure handling), §16 (testing), §20 (M2 line). The M1 plan (`docs/superpowers/plans/2026-10-11-m1-foundation.md`) shows the conventions the code below follows.

**Scope notes (rulings made while planning; each is cheap to revisit):**
- **In scope:**
  - routes `/`, `/YYYY/MM/DD/`, `/archive/`, `rss.xml`, sitemap and 404
  - visual kinds `vega-lite`, `mermaid`, `table`, `image-ref` (from M1) plus the new `dashboard`
  - token presets `pulse`, `paper` and `terminal`
  - `pulse site context` and `pulse tokens check`
  - three sample reports in `examples/`, which acts as a demo instance
- **Deferred:**
  - `/threads/`, `/entities/` and `/trends/` need the M3 history store.
  - `/health/` needs M6 run records.
  - The `motion` and `custom-html` visual kinds arrive with `pulse shoot`/gifski (M6) and the design lint (M4).
  - `pulse site build` (an orchestrator over the two steps here) and npm publishing of the site, tokens and contracts packages are M6.
- **Visual-to-block placement:** visuals gain an optional `block` field (a block id of the item's type). Deep-dive blocks with no detail fields (benchmarks, timelines, results) then have content. `pulse validate` checks the id.
- **Mermaid:** rendered client-side by an island with an alt-text plus source fallback. `astro-mermaid` only transforms Markdown code fences, and reports are JSON. This settles spec risk 8.
- **Images:** hotlinked `<img>`, not Astro `<Image>`, because optimizing would copy third-party images whose licence may not allow it (spec §10.3: "hotlinked, copied only if license allows"). Astro's optional `sharp` optimizer (LGPL libvips) is therefore not installed.
- **Search:** the front page repeats the latest edition, so it stays out of the Pagefind index and links to the dated page as canonical.
- **Engine data lookup:** `@pulseai/contracts` and `@pulseai/tokens` locate `schema/` and `tokens/` through their own package names, because Vite bundles them into the site's server build. That is what `import.meta.url` cannot survive.
- **Sample content:** the three example reports set `meta.sample: true`, use fictional organizations and IANA example domains, and render a "Sample edition" banner. Real reports replace them in M6.

## Global Constraints

Everything in the M1 plan's Global Constraints still applies (latest versions via `uv add`/`pnpm add` without pins, SHA-pinned actions, workflow hardening, no hardcoding, schema rules, ids, generated code, Python and TypeScript style, Conventional Commits with the `Co-Authored-By` trailer, CLI output and exit codes, `ruff format` before `ruff check`). In addition:

- **Run TypeScript with plain `node`.** Node 24+ strips types, so scripts are `.ts` files run as `node scripts/x.ts`. Use only erasable syntax (no `enum`, no parameter properties, no `namespace` values) and explicit `.ts` extensions in relative imports. Node refuses to strip types under `node_modules`, so M6 compiles these packages before publishing. In the workspace they run from source.
- **No hardcoded copy.** Every user-visible string comes from `locales/<lang>.json` through `t()`. A Vitest test fails on any literal `t("…")` key missing from `en.json` or `tr.json`. Key families: `ui.*` (frame), `blocks.<block id>`, `fields.<detail field>`, and enum values (`confidence.*`, `rings.*`, `tiers.*`, `kinds.*`, `changelog.*`, `severity.*`, `difficulty.*`, `weights.*`, `hosts.*`, `modes.*`, `stats.*`). Locale keys are lowercase, so source tiers map to `tiers.<tier lowercased>`.
- **No raw design values in the site.** Colors, fonts, radii and spacing come from tokens as `var(--pulse-…)`. A Vitest test fails on hex, `rgb()`, `hsl()` or `oklch()` literals under `packages/site/src`. Chart and diagram themes are built from resolved token maps, never from literals.
- **Option lists come from schemas or registries.** Ring order, confidence values and tiers are read from enums in the context's schemas; section order from the sections registry; block order from the item-types registry.
- **Progressive enhancement:** every page is complete without JavaScript. Charts fall back to an open data table, diagrams to alt text plus source, filters and the theme switch stay hidden, and Auto theme follows the OS through CSS. Client code lives in `packages/site/src/client/` as custom elements loaded by component `<script>` tags. There is no UI framework.
- **Accessibility:** WCAG 2.2 AA. axe-core reports zero `serious`/`critical` violations in light, dark and mobile. Native `<details>`/`<summary>`, one `<h1>` per page, visible focus rings, `prefers-reduced-motion` respected.
- **Determinism:** the site build is a pure function of the engine version and the instance directory (context file, generated tokens, reports). No network access during the build.
- **Biome on Astro files:** Biome formats and lints `.astro` frontmatter, but cannot see template usage, so `noUnusedImports` and `noUnusedVariables` are off for `**/*.astro` (Task 7). `astro check` type-checks them, and the site's `tsc` checks its `.ts` files and tests. Run `pnpm biome check --write .` before committing TypeScript, JSON, CSS or Astro files.
- **Generated files:** `packages/contracts/src/generated/` is written by `pnpm --filter @pulseai/contracts generate`; CI runs `generate:check`. `examples/.pulse/` and `examples/dist/` are build outputs and are git-ignored.
- **Playwright runs in the pinned container** `mcr.microsoft.com/playwright:v1.64.0-noble`, whose version must equal `@playwright/test`. Renovate groups the two (Task 17).

## Review Focus

1. **A report or registry the frame does not expect.** An unknown section or item type, a block id with no renderer, an item type with no component, or a missing dynamic label must fail the build with the report file and JSON path, or degrade visibly but safely. → Task 7 `rejects an unknown section with the file and path`, `checks each item's detail against its type's schema`; Task 10 `falls back to GenericDetail for a component that does not exist`, `renders assigned visuals for a block the component does not know`.
2. **A broken visual spec** (invalid Vega-Lite, Mermaid syntax error) must leave the page usable: the data table or source stays visible, the element is marked `data-error`, and other visuals still render. → Task 15 `a broken chart keeps its table and does not stop other charts`, `a broken diagram keeps its alt text and source`.
3. **No JavaScript, and print.** Every item stays reachable and readable, charts show tables, and printing expands every item. → Task 15 `every item is reachable and every chart shows its data`, `expands every item`.
4. **Theme edge cases.** Storage that throws, an invalid `?theme=` value, OS dark with a stored light choice, and switching while charts are on screen must all give the right theme without errors. → Task 15 `survives storage that throws`, `honours a valid theme query and ignores an invalid one`, `remembers the reader's pick across pages`, `re-themes charts when the theme changes`.
5. **Deployment URL shapes.** A site URL with a path (a GitHub Pages project site) must prefix every link, asset and the search bundle. No site URL must build without RSS or sitemap, and with root-relative links. → Task 7 `siteLocation` tests; Task 15 runs every browser test under `/PulseAI/`, including `publishes a feed with absolute links below the base path` and `finds editions with search, without duplicating the front page`.
6. **Empty and extreme content.** A report with no items in a section, no TL;DR, no radar or no signals must not render empty headings, and a very long title must not break the layout on mobile. → Task 9 `renders nothing for empty regions`; Task 13 `renders nothing for empty signals and corrections`; Task 16 `item-long-title.png` on mobile.

---

## File Structure

```
schema/report.schema.json                        # Task 1   dashboard visual, visual.block
schema/site-context.schema.json                  # Task 3   context bundle contract
schema/tokens-resolved.schema.json               # Task 5   resolved token map contract
schema/config.schema.json, defaults/pulse.config.yaml   # Task 6   quality.cvd_simulations
locales/{en,tr}.json                             # Task 1 (blocks, brief fields), Task 7 (site strings)
packages/cli/src/pulseai/report/validate.py      # Task 1   nested visuals, block ids, tile spans
packages/cli/src/pulseai/registry/checks.py      # Task 1   block and field label keys
packages/cli/src/pulseai/site/                   # Task 3   pulse site context
packages/cli/src/pulseai/tokens/                 # Task 6   pulse tokens check (ColorAide)
packages/cli/src/pulseai/cli.py                  # Tasks 3, 6
packages/cli/tests/                              # Tasks 1, 3, 4, 6 (incl. the exit-code matrix)
packages/contracts/scripts/generate-types.ts     # Task 2
packages/contracts/src/{index.ts,generated/}     # Task 2   types, package-name schema lookup
examples/pulse.config.yaml, examples/reports/    # Tasks 3, 4   demo instance, three sample editions
tokens/base/**, tokens/themes/{pulse,paper,terminal}/   # Task 5
packages/tokens/                                 # Tasks 5, 6   layering, overrides, resolution, CSS, preset gate
packages/site/{package.json,tsconfig.json,astro.config.ts,vitest.config.ts}   # Task 7
packages/site/scripts/pulse-site.ts              # Task 7   build|dev|preview|check wrapper
packages/site/scripts/playwright-docker.ts       # Task 15
packages/site/src/lib/                           # Tasks 7, 8, 10, 11, 12
packages/site/src/client/                        # Tasks 7, 8, 12   custom elements
packages/site/src/layouts/Base.astro, src/styles/global.css   # Task 7
packages/site/src/components/frame/              # Tasks 7, 9, 12, 13
packages/site/src/components/visuals/            # Task 8
packages/site/src/components/blocks/             # Tasks 8, 10
packages/site/src/components/items/              # Tasks 10, 11
packages/site/src/pages/                         # Tasks 7, 13, 14
packages/site/test/                              # Vitest, one file per task (Tasks 7–13)
packages/site/e2e/, playwright.config.ts         # Tasks 15, 16
.github/workflows/{ci,dependency-review}.yml, .github/repository.yml   # Tasks 7, 8, 17
renovate.json, release-please-config.json, .release-please-manifest.json   # Task 17
docs/site.md, docs/adr/0002-site-rendering.md, README.md, CONTRIBUTING.md   # Task 17
biome.json, .gitignore, package.json, pnpm-workspace.yaml   # Tasks 2, 3, 5–7, 15
```

---
### Task 1: Dashboard visuals, visual-to-block placement, block and field labels

**Files:**
- Modify: `schema/report.schema.json` (`$defs.visual`, the four leaf visual defs, new dashboard defs)
- Modify: `schema/examples/report/invalid-schema.json` (append cases)
- Modify: `packages/cli/tests/data/report-semantic-cases.json` (append cases)
- Modify: `packages/cli/src/pulseai/report/validate.py` (`_visuals`, new `_check_visual_placement`)
- Modify: `packages/cli/src/pulseai/registry/checks.py` (`_label_keys`)
- Modify: `locales/en.json`, `locales/tr.json` (add `blocks.*` and brief `fields.*`)
- Regenerate: `packages/cli/src/pulseai/models/report.py`
- Test: `packages/cli/tests/test_report_validate.py`, `packages/cli/tests/test_checks.py`

**Interfaces:**
- Produces (schema): `DashboardVisual` `{kind: "dashboard", id, title, alt, source_note, block?, columns: 1..4, tiles: DashboardTile[1..12]}`. `DashboardTile` is `StatTile {tile: "stat", span?, label, value, unit?, delta?, series?}` or `VisualTile {tile: "visual", span?, visual: LeafVisual}`. `LeafVisual` is one of the four M1 kinds. Every visual gains optional `block` (an `id`).
- Produces (rules): `_visuals(report)` also yields the leaf visuals inside dashboards, so unique-id, remote-data and table-width rules cover them. `_check_visual_placement` enforces: an item visual's `block` must be one of its type's `blocks`; front-page and dashboard-tile visuals cannot set `block`; a tile's `span` cannot exceed the dashboard's `columns`.
- Produces (labels): `pulse registry check` requires `blocks.<id>` for every block and `fields.<name>` for every `brief_fields` entry in the item-types registry.

- [ ] **Step 1: Write the failing schema cases**

Append to `schema/examples/report/invalid-schema.json` (keep the array valid JSON):

```json
  {
    "name": "dashboard without tiles",
    "patch": [
      {
        "op": "add",
        "path": "/front_page/-",
        "value": {
          "kind": "dashboard", "id": "board", "title": "Board", "alt": "Empty board",
          "source_note": "Report", "columns": 2, "tiles": []
        }
      }
    ]
  },
  {
    "name": "dashboard with five columns",
    "patch": [
      {
        "op": "add",
        "path": "/front_page/-",
        "value": {
          "kind": "dashboard", "id": "board", "title": "Board", "alt": "Board",
          "source_note": "Report", "columns": 5,
          "tiles": [{ "tile": "stat", "label": "Items", "value": 3 }]
        }
      }
    ]
  },
  {
    "name": "dashboard tile of unknown kind",
    "patch": [
      {
        "op": "add",
        "path": "/front_page/-",
        "value": {
          "kind": "dashboard", "id": "board", "title": "Board", "alt": "Board",
          "source_note": "Report", "columns": 2,
          "tiles": [{ "tile": "chart", "label": "Items", "value": 3 }]
        }
      }
    ]
  },
  {
    "name": "dashboard nested in a dashboard",
    "patch": [
      {
        "op": "add",
        "path": "/front_page/-",
        "value": {
          "kind": "dashboard", "id": "outer", "title": "Outer", "alt": "Outer",
          "source_note": "Report", "columns": 2,
          "tiles": [
            {
              "tile": "visual",
              "visual": {
                "kind": "dashboard", "id": "inner", "title": "Inner", "alt": "Inner",
                "source_note": "Report", "columns": 1,
                "tiles": [{ "tile": "stat", "label": "Items", "value": 3 }]
              }
            }
          ]
        }
      }
    ]
  },
  {
    "name": "visual block is not an id",
    "patch": [{ "op": "add", "path": "/items/0/visuals/0/block", "value": "Not An Id" }]
  }
```

- [ ] **Step 2: Write the failing semantic cases**

Append to `packages/cli/tests/data/report-semantic-cases.json` (the minimal report's `items/0` is an `industry` item whose blocks are `summary_facts`, `timeline` and `builder_impact`, and whose first visual is the table `regions-table`):

```json
  {
    "name": "visual block is not one of the item type's blocks",
    "patch": [{ "op": "add", "path": "/items/0/visuals/0/block", "value": "benchmarks" }],
    "expect": "block 'benchmarks' is not one of the 'industry' blocks"
  },
  {
    "name": "front-page visual names a block",
    "patch": [
      {
        "op": "add",
        "path": "/front_page/-",
        "value": {
          "kind": "table", "id": "front-table", "title": "Front", "alt": "Front table",
          "source_note": "Report", "block": "timeline", "columns": ["A"], "rows": [["x"]]
        }
      }
    ],
    "expect": "front-page visuals are not in an item"
  },
  {
    "name": "dashboard tile wider than the dashboard",
    "patch": [
      {
        "op": "add",
        "path": "/front_page/-",
        "value": {
          "kind": "dashboard", "id": "board", "title": "Board", "alt": "Board",
          "source_note": "Report", "columns": 2,
          "tiles": [{ "tile": "stat", "span": 3, "label": "Items", "value": 3 }]
        }
      }
    ],
    "expect": "span 3 is wider than the dashboard's 2 columns"
  },
  {
    "name": "duplicate visual id inside a dashboard",
    "patch": [
      {
        "op": "add",
        "path": "/front_page/-",
        "value": {
          "kind": "dashboard", "id": "board", "title": "Board", "alt": "Board",
          "source_note": "Report", "columns": 1,
          "tiles": [
            {
              "tile": "visual",
              "visual": {
                "kind": "table", "id": "regions-table", "title": "Again", "alt": "Again",
                "source_note": "Report", "columns": ["A"], "rows": [["x"]]
              }
            }
          ]
        }
      }
    ],
    "expect": "duplicate visual id 'regions-table'"
  },
  {
    "name": "table row width inside a dashboard",
    "patch": [
      {
        "op": "add",
        "path": "/front_page/-",
        "value": {
          "kind": "dashboard", "id": "board", "title": "Board", "alt": "Board",
          "source_note": "Report", "columns": 1,
          "tiles": [
            {
              "tile": "visual",
              "visual": {
                "kind": "table", "id": "tile-table", "title": "T", "alt": "T",
                "source_note": "Report", "columns": ["A"], "rows": [["x", "y"]]
              }
            }
          ]
        }
      }
    ],
    "expect": "2 cells, expected 1"
  },
  {
    "name": "remote chart data inside a dashboard",
    "patch": [
      {
        "op": "add",
        "path": "/front_page/-",
        "value": {
          "kind": "dashboard", "id": "board", "title": "Board", "alt": "Board",
          "source_note": "Report", "columns": 1,
          "tiles": [
            {
              "tile": "visual",
              "visual": {
                "kind": "vega-lite", "id": "tile-chart", "title": "C", "alt": "C",
                "source_note": "Report",
                "spec": { "data": { "url": "https://example.org/data.json" }, "mark": "bar" }
              }
            }
          ]
        }
      }
    ],
    "expect": "remote chart data"
  },
  {
    "name": "visual inside a dashboard names a block",
    "patch": [
      {
        "op": "add",
        "path": "/front_page/-",
        "value": {
          "kind": "dashboard", "id": "board", "title": "Board", "alt": "Board",
          "source_note": "Report", "columns": 1,
          "tiles": [
            {
              "tile": "visual",
              "visual": {
                "kind": "table", "id": "tile-table", "title": "T", "alt": "T",
                "source_note": "Report", "block": "timeline", "columns": ["A"], "rows": [["x"]]
              }
            }
          ]
        }
      }
    ],
    "expect": "visuals inside a dashboard cannot name a block"
  }
```

Add to `packages/cli/tests/test_report_validate.py`:

```python
def test_a_dashboard_with_stat_and_visual_tiles_is_valid(minimal: dict[str, Any]) -> None:
    minimal["front_page"].append(
        {
            "kind": "dashboard",
            "id": "board",
            "title": "Today at a glance",
            "alt": "Two stat tiles and a table",
            "source_note": "This report",
            "columns": 3,
            "tiles": [
                {"tile": "stat", "label": "Items", "value": 2, "delta": 1, "series": [1, 2]},
                {"tile": "stat", "label": "Price", "value": 3.5, "unit": "USD"},
                {
                    "tile": "visual",
                    "span": 3,
                    "visual": {
                        "kind": "table",
                        "id": "board-table",
                        "title": "Items",
                        "alt": "Items table",
                        "source_note": "This report",
                        "columns": ["Item"],
                        "rows": [["one"], ["two"]],
                    },
                },
            ],
        }
    )
    assert validate_report(minimal) == []


def test_a_visual_may_name_one_of_its_item_types_blocks(minimal: dict[str, Any]) -> None:
    minimal["items"][0]["visuals"][0]["block"] = "timeline"
    assert validate_report(minimal) == []
```

Add to `packages/cli/tests/test_checks.py` (it already imports `check_registries`; add `json` and `Path` imports if missing):

```python
def test_block_and_brief_field_labels_must_exist(engine_copy: Path) -> None:
    for name in ("en", "tr"):
        path = engine_copy / "locales" / f"{name}.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        del doc["strings"]["blocks.timeline"]
        del doc["strings"]["fields.who"]
        path.write_text(json.dumps(doc), encoding="utf-8")
    messages = [f"{i.where}: {i.message}" for i in check_registries() if i.level == "error"]
    assert any("missing locale string 'blocks.timeline'" in m for m in messages), messages
    assert any("missing locale string 'fields.who'" in m for m in messages), messages
    assert any("/blocks/" in m for m in messages)
    assert any("/brief_fields/" in m for m in messages)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest packages/cli/tests/test_report_validate.py packages/cli/tests/test_checks.py -q`
Expected: FAIL. The dashboard cases are rejected as an unknown visual shape, or accepted when they should not be. The block cases report nothing. `test_block_and_brief_field_labels_must_exist` raises `KeyError: 'blocks.timeline'` because the keys do not exist yet.

- [ ] **Step 4: Extend the report schema**

In `schema/report.schema.json` replace `$defs.visual` with:

```json
    "visual": {
      "oneOf": [
        { "$ref": "#/$defs/vegaLiteVisual" },
        { "$ref": "#/$defs/mermaidVisual" },
        { "$ref": "#/$defs/tableVisual" },
        { "$ref": "#/$defs/imageRefVisual" },
        { "$ref": "#/$defs/dashboardVisual" }
      ]
    },
    "leafVisual": {
      "description": "A visual that can sit inside a dashboard tile (any kind except dashboard).",
      "oneOf": [
        { "$ref": "#/$defs/vegaLiteVisual" },
        { "$ref": "#/$defs/mermaidVisual" },
        { "$ref": "#/$defs/tableVisual" },
        { "$ref": "#/$defs/imageRefVisual" }
      ]
    },
    "visualBlock": {
      "$ref": "#/$defs/id",
      "description": "Deep-dive block of the item's type to render this visual in. Without it the visual renders after the item's facts."
    },
    "span": { "type": "integer", "minimum": 1, "maximum": 4 },
    "dashboardVisual": {
      "title": "DashboardVisual",
      "type": "object",
      "additionalProperties": false,
      "required": ["kind", "id", "title", "alt", "source_note", "columns", "tiles"],
      "properties": {
        "kind": { "const": "dashboard" },
        "id": { "$ref": "#/$defs/slug" },
        "title": { "$ref": "#/$defs/shortText" },
        "alt": { "$ref": "#/$defs/alt" },
        "source_note": { "$ref": "#/$defs/shortText" },
        "block": { "$ref": "#/$defs/visualBlock" },
        "columns": { "type": "integer", "minimum": 1, "maximum": 4 },
        "tiles": {
          "type": "array",
          "minItems": 1,
          "maxItems": 12,
          "items": { "$ref": "#/$defs/dashboardTile" }
        }
      }
    },
    "dashboardTile": {
      "oneOf": [{ "$ref": "#/$defs/statTile" }, { "$ref": "#/$defs/visualTile" }]
    },
    "statTile": {
      "title": "StatTile",
      "type": "object",
      "additionalProperties": false,
      "required": ["tile", "label", "value"],
      "properties": {
        "tile": { "const": "stat" },
        "span": { "$ref": "#/$defs/span" },
        "label": { "$ref": "#/$defs/shortText" },
        "value": { "type": ["string", "number"] },
        "unit": { "type": "string", "minLength": 1, "maxLength": 20 },
        "delta": { "type": "number" },
        "series": { "type": "array", "items": { "type": "number" } }
      }
    },
    "visualTile": {
      "title": "VisualTile",
      "type": "object",
      "additionalProperties": false,
      "required": ["tile", "visual"],
      "properties": {
        "tile": { "const": "visual" },
        "span": { "$ref": "#/$defs/span" },
        "visual": { "$ref": "#/$defs/leafVisual" }
      }
    },
```

In each of `vegaLiteVisual`, `mermaidVisual`, `tableVisual` and `imageRefVisual`, add this property after `source_note`:

```json
        "block": { "$ref": "#/$defs/visualBlock" },
```

- [ ] **Step 5: Regenerate the Python models**

Run: `uv run python scripts/generate_models.py`
Expected: `packages/cli/src/pulseai/models/report.py` gains `DashboardVisual`, `StatTile`, `VisualTile` and `block` fields; no other module changes.

- [ ] **Step 6: Validate nested visuals and block placement**

In `packages/cli/src/pulseai/report/validate.py`, add constants below `TABLE_KIND`:

```python
DASHBOARD_KIND = "dashboard"
VISUAL_TILE = "visual"
```

Replace `_visuals` with:

```python
def _with_nested(where: str, visual: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """A visual followed by the leaf visuals in its dashboard tiles, if it is a dashboard."""
    yield where, visual
    if visual["kind"] == DASHBOARD_KIND:
        for index, tile in enumerate(visual["tiles"]):
            if tile["tile"] == VISUAL_TILE:
                yield f"{where}/tiles/{index}/visual", tile["visual"]


def _visuals(report: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for index, visual in enumerate(report["front_page"]):
        yield from _with_nested(f"front_page/{index}", visual)
    for where, item in _items(report):
        for index, visual in enumerate(item["visuals"]):
            yield from _with_nested(f"{where}/visuals/{index}", visual)
```

Add after `_check_visuals`:

```python
def _check_dashboard(where: str, visual: dict[str, Any]) -> Iterator[Issue]:
    for index, tile in enumerate(visual["tiles"]):
        span = tile.get("span", 1)
        if span > visual["columns"]:
            yield _error(
                f"{where}/tiles/{index}/span",
                f"span {span} is wider than the dashboard's {visual['columns']} columns",
            )
        if tile["tile"] == VISUAL_TILE and "block" in tile["visual"]:
            yield _error(
                f"{where}/tiles/{index}/visual/block",
                "visuals inside a dashboard cannot name a block",
            )


def _check_visual_placement(report: dict[str, Any], ctx: _Context) -> Iterator[Issue]:
    for index, visual in enumerate(report["front_page"]):
        where = f"front_page/{index}"
        if "block" in visual:
            yield _error(
                f"{where}/block", "front-page visuals are not in an item, so they cannot name a block"
            )
        if visual["kind"] == DASHBOARD_KIND:
            yield from _check_dashboard(where, visual)
    for item_where, item in _items(report):
        item_type = ctx.item_types.get(item["type"])
        for index, visual in enumerate(item["visuals"]):
            where = f"{item_where}/visuals/{index}"
            block = visual.get("block")
            # An unknown item type is reported by _check_registry_refs already.
            if block is not None and item_type is not None and block not in item_type["blocks"]:
                yield _error(
                    f"{where}/block",
                    f"block {block!r} is not one of the {item['type']!r} blocks: "
                    f"{', '.join(item_type['blocks'])}",
                )
            if visual["kind"] == DASHBOARD_KIND:
                yield from _check_dashboard(where, visual)
```

In `validate_report`, add `*_check_visual_placement(report, ctx),` to the `issues` list right after `*_check_visuals(report),`.

- [ ] **Step 7: Require block and brief-field labels**

In `packages/cli/src/pulseai/registry/checks.py`, replace the item-type loop at the end of `_label_keys` with:

```python
    for i, item_type in enumerate(item_types):
        yield f"item_types/{i}/label", item_type["label"]
        # Block and field labels follow the blocks.<id> and fields.<name> key convention.
        for j, block in enumerate(item_type["blocks"]):
            yield f"item_types/{i}/blocks/{j}", f"blocks.{block}"
        for j, field in enumerate(item_type["brief_fields"]):
            yield f"item_types/{i}/brief_fields/{j}", f"fields.{field}"
```

- [ ] **Step 8: Add the block and brief-field strings**

Add these entries to `strings` in `locales/en.json`:

```json
    "blocks.key_facts": "Key facts",
    "blocks.benchmarks": "Benchmarks",
    "blocks.price_comparison": "Price comparison",
    "blocks.try_it": "Try it",
    "blocks.archive_history": "History",
    "blocks.changelog": "Changelog",
    "blocks.cadence": "Release cadence",
    "blocks.verdict": "Verdict",
    "blocks.snippet": "Snippet",
    "blocks.migration_notes": "Migration notes",
    "blocks.tldr": "TL;DR",
    "blocks.plain_explanation": "In plain words",
    "blocks.problem_and_idea": "Problem and key idea",
    "blocks.method": "Method",
    "blocks.results": "Results",
    "blocks.critical_review": "Critical review",
    "blocks.reproducibility": "Reproducibility",
    "blocks.takeaway": "Takeaway",
    "blocks.reading_guide": "Reading guide",
    "blocks.figures": "Figures",
    "blocks.related": "Related work",
    "blocks.key_points": "Key points",
    "blocks.reading_time": "Reading time",
    "blocks.stars_trend": "Stars trend",
    "blocks.facts": "Facts",
    "blocks.alternatives": "Alternatives",
    "blocks.quickstart": "Quickstart",
    "blocks.severity": "Severity",
    "blocks.versions": "Affected and fixed versions",
    "blocks.exploitation": "Exploitation",
    "blocks.fix": "Fix",
    "blocks.summary_facts": "Who, what, how much",
    "blocks.timeline": "Timeline",
    "blocks.builder_impact": "Impact on builders",
    "blocks.rank_changes": "Rank changes",
    "blocks.reliability": "Reliability",
    "fields.org": "Organization",
    "fields.model": "Model",
    "fields.product": "Product",
    "fields.version": "Version",
    "fields.tldr": "TL;DR",
    "fields.publication": "Publication",
    "fields.reading_minutes": "Reading time",
    "fields.full_name": "Repository",
    "fields.stars": "Stars",
    "fields.advisory_id": "Advisory",
    "fields.severity": "Severity",
    "fields.who": "Who",
    "fields.board": "Leaderboard"
```

Add the same keys to `locales/tr.json`:

```json
    "blocks.key_facts": "Temel bilgiler",
    "blocks.benchmarks": "Kıyaslamalar",
    "blocks.price_comparison": "Fiyat karşılaştırması",
    "blocks.try_it": "Deneyin",
    "blocks.archive_history": "Geçmiş",
    "blocks.changelog": "Değişiklik günlüğü",
    "blocks.cadence": "Yayın sıklığı",
    "blocks.verdict": "Değerlendirme",
    "blocks.snippet": "Örnek kod",
    "blocks.migration_notes": "Geçiş notları",
    "blocks.tldr": "Özet",
    "blocks.plain_explanation": "Sade anlatımla",
    "blocks.problem_and_idea": "Problem ve ana fikir",
    "blocks.method": "Yöntem",
    "blocks.results": "Sonuçlar",
    "blocks.critical_review": "Eleştirel değerlendirme",
    "blocks.reproducibility": "Tekrarlanabilirlik",
    "blocks.takeaway": "Çıkarım",
    "blocks.reading_guide": "Okuma rehberi",
    "blocks.figures": "Şekiller",
    "blocks.related": "İlgili çalışmalar",
    "blocks.key_points": "Ana noktalar",
    "blocks.reading_time": "Okuma süresi",
    "blocks.stars_trend": "Yıldız eğilimi",
    "blocks.facts": "Bilgiler",
    "blocks.alternatives": "Alternatifler",
    "blocks.quickstart": "Hızlı başlangıç",
    "blocks.severity": "Önem derecesi",
    "blocks.versions": "Etkilenen ve düzeltilen sürümler",
    "blocks.exploitation": "İstismar durumu",
    "blocks.fix": "Düzeltme",
    "blocks.summary_facts": "Kim, ne, ne kadar",
    "blocks.timeline": "Zaman çizelgesi",
    "blocks.builder_impact": "Geliştiricilere etkisi",
    "blocks.rank_changes": "Sıralama değişiklikleri",
    "blocks.reliability": "Güvenilirlik",
    "fields.org": "Kuruluş",
    "fields.model": "Model",
    "fields.product": "Ürün",
    "fields.version": "Sürüm",
    "fields.tldr": "Özet",
    "fields.publication": "Yayın",
    "fields.reading_minutes": "Okuma süresi",
    "fields.full_name": "Depo",
    "fields.stars": "Yıldız",
    "fields.advisory_id": "Bildirim",
    "fields.severity": "Önem derecesi",
    "fields.who": "Kim",
    "fields.board": "Sıralama tablosu"
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `uv run pytest packages/cli/tests -q && uv run python scripts/generate_models.py --check && uv run pulse registry check`
Expected: all tests pass, models are current, and `Registries are consistent.` is printed.

Run: `pnpm --filter @pulseai/contracts test`
Expected: PASS (the `compiles report` test covers the new defs in Zod).

- [ ] **Step 10: Lint and commit**

```bash
uv run ruff format . && uv run ruff check . && uv run pyright && pnpm biome check --write schema locales packages/cli/tests/data
git add schema/report.schema.json schema/examples/report/invalid-schema.json packages/cli locales
git commit -m "feat(schema): add dashboard visuals and visual-to-block placement

Dashboards hold stat tiles and leaf visuals. Visuals may name a deep-dive
block of their item's type. pulse validate checks nested visuals, block ids
and tile spans; pulse registry check requires block and brief-field labels.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 2: TypeScript types generated from the schemas

**Files:**
- Create: `packages/contracts/scripts/generate-types.ts`
- Create (generated): `packages/contracts/src/generated/**/*.ts`
- Create: `packages/contracts/test/generated.test.ts`
- Modify: `packages/contracts/src/index.ts`, `packages/contracts/package.json`, `packages/contracts/tsconfig.json`, `biome.json`

**Interfaces:**
- Consumes: `loadSchemas()` from `packages/contracts/src/index.ts` (M1).
- Produces:
  - One namespace of types per schema key. The name is the PascalCase key plus `Schema`: `ReportSchema`, `SectionsSchema`, `ItemTypesSchema`, `ConfigSchema`, `LocaleSchema`, `ItemTypesPaperSchema`, …, and later `SiteContextSchema` (Task 3) and `TokensResolvedSchema` (Task 5). All are re-exported from `@pulseai/contracts`.
  - Type names come from schema `title`s, e.g. `ReportSchema.Report`, `ReportSchema.Item`, `ReportSchema.DashboardVisual`, `SectionsSchema.Section`, `ItemTypesSchema.ItemType`, `ConfigSchema.PulseConfig`, `ConfigSchema.ThemeOverrides`, `ItemTypesReleaseSchema.ReleaseDetail`.
  - `generateTypes(): Promise<Map<string, string>>` and `OUT_DIR` from `scripts/generate-types.ts`, plus package scripts `generate` and `generate:check`.
  - `DEFAULT_SCHEMA_DIR` is found through the package's own name (`require.resolve("@pulseai/contracts/package.json")`), not `import.meta.url`. The path then stays right when Vite bundles this module into the site's server build (Task 7). The package exports `./package.json` for that.
- Every later task that changes a schema reruns `pnpm --filter @pulseai/contracts generate`; the drift test fails otherwise.

- [ ] **Step 1: Write the failing tests**

`packages/contracts/test/generated.test.ts`:

```ts
import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, expectTypeOf, it } from "vitest";
import { generateTypes, OUT_DIR } from "../scripts/generate-types.ts";
import { DEFAULT_SCHEMA_DIR, type ReportSchema, type SectionsSchema } from "../src/index.ts";

function readTree(dir: string): Map<string, string> {
  const files = new Map<string, string>();
  for (const rel of readdirSync(dir, { recursive: true, encoding: "utf8" })) {
    if (rel.endsWith(".ts")) {
      files.set(rel.split("\\").join("/"), readFileSync(join(dir, rel), "utf8"));
    }
  }
  return files;
}

describe("generated types", () => {
  it("are current (run: pnpm --filter @pulseai/contracts generate)", async () => {
    const expected = await generateTypes();
    const actual = readTree(OUT_DIR);
    expect([...actual.keys()].sort()).toEqual([...expected.keys()].sort());
    for (const [file, text] of expected) {
      expect(actual.get(file), file).toBe(text);
    }
  });

  it("names types after schema titles", () => {
    expectTypeOf<ReportSchema.Report["schema_version"]>().toEqualTypeOf<1>();
    expectTypeOf<ReportSchema.Item["confidence"]>().toEqualTypeOf<
      "confirmed" | "reported" | "rumor"
    >();
    expectTypeOf<ReportSchema.DashboardVisual["kind"]>().toEqualTypeOf<"dashboard">();
    expectTypeOf<SectionsSchema.Section["order"]>().toEqualTypeOf<number>();
  });
});

describe("schema directory", () => {
  it("is found through the package name, so bundling this module keeps it right", () => {
    expect(DEFAULT_SCHEMA_DIR).toBe(
      resolve(fileURLToPath(new URL("../../../schema", import.meta.url))),
    );
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pnpm --filter @pulseai/contracts test`
Expected: FAIL with `Cannot find module '../scripts/generate-types.ts'`.

- [ ] **Step 3: Add the generator dependency and scripts**

Run: `pnpm --filter @pulseai/contracts add -D json-schema-to-typescript`

In `packages/contracts/package.json`, set `exports` and `scripts` to:

```json
  "exports": {
    ".": "./src/index.ts",
    "./package.json": "./package.json"
  },
  "scripts": {
    "generate": "node scripts/generate-types.ts",
    "generate:check": "node scripts/generate-types.ts --check",
    "typecheck": "tsc -p tsconfig.json",
    "test": "vitest run"
  },
```

In `packages/contracts/tsconfig.json`, set `"include": ["src", "test", "scripts"]`.

In `biome.json`, add `"!packages/contracts/src/generated"` to `files.includes`. It is generated code, like the Python models.

- [ ] **Step 4: Write the generator**

`packages/contracts/scripts/generate-types.ts`:

```ts
/**
 * Generate TypeScript types from schema/*.schema.json, the single source of truth.
 *
 *   node scripts/generate-types.ts          # rewrite src/generated/
 *   node scripts/generate-types.ts --check  # exit 1 when src/generated/ is stale
 */
import { mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";
import { loadSchemas } from "../src/index.ts";

export const OUT_DIR = fileURLToPath(new URL("../src/generated/", import.meta.url));

const HEADER =
  "/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */\n\n";

type CompileInput = Parameters<typeof compile>[0];

/** "item-types/paper" -> "ItemTypesPaperSchema". */
export function namespaceName(key: string): string {
  const words = key.split(/[/_-]/).filter((word) => word.length > 0);
  return `${words.map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join("")}Schema`;
}

/** Generated file contents keyed by path relative to OUT_DIR ("report.ts", "item-types/paper.ts"). */
export async function generateTypes(): Promise<Map<string, string>> {
  const files = new Map<string, string>();
  const barrel: string[] = [];
  for (const [key, schema] of loadSchemas()) {
    const types = await compile(schema as CompileInput, key, {
      bannerComment: "",
      additionalProperties: false,
      strictIndexSignatures: true,
      unreachableDefinitions: false,
      style: { printWidth: 100 },
    });
    files.set(`${key}.ts`, HEADER + types);
    barrel.push(`export type * as ${namespaceName(key)} from "./${key}.ts";`);
  }
  files.set("index.ts", `${HEADER + barrel.join("\n")}\n`);
  return files;
}

function readTree(dir: string): Map<string, string> {
  const files = new Map<string, string>();
  let entries: string[];
  try {
    entries = readdirSync(dir, { recursive: true, encoding: "utf8" });
  } catch {
    return files;
  }
  for (const rel of entries) {
    if (rel.endsWith(".ts")) {
      files.set(rel.split("\\").join("/"), readFileSync(join(dir, rel), "utf8"));
    }
  }
  return files;
}

async function main(argv: string[]): Promise<number> {
  const files = await generateTypes();
  if (argv.includes("--check")) {
    const current = readTree(OUT_DIR);
    const names = new Set([...files.keys(), ...current.keys()]);
    const stale = [...names].filter((name) => files.get(name) !== current.get(name)).sort();
    if (stale.length > 0) {
      console.error(`stale generated types: ${stale.join(", ")}`);
      console.error("run: pnpm --filter @pulseai/contracts generate");
      return 1;
    }
    return 0;
  }
  rmSync(OUT_DIR, { recursive: true, force: true });
  for (const [rel, text] of files) {
    const target = join(OUT_DIR, rel);
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, text);
  }
  return 0;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}
```

- [ ] **Step 5: Find the schemas through the package name and re-export the types**

Replace `packages/contracts/src/index.ts` with:

```ts
import { readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve, sep } from "node:path";
import { z } from "zod";

export type JsonSchema = Parameters<typeof z.fromJSONSchema>[0];

const SUFFIX = ".schema.json";

/**
 * The engine's schema/ directory. It is found through this package's own name, not this file's
 * location, so it stays right when a bundler (the site's server build) moves this module.
 */
export const DEFAULT_SCHEMA_DIR = resolve(
  dirname(createRequire(import.meta.url).resolve("@pulseai/contracts/package.json")),
  "../../schema",
);

/** Every *.schema.json under dir, keyed by relative path without the suffix ("item-types/paper"). */
export function loadSchemas(dir: string = DEFAULT_SCHEMA_DIR): Map<string, JsonSchema> {
  const schemas = new Map<string, JsonSchema>();
  const entries = readdirSync(dir, { recursive: true, encoding: "utf8" });
  for (const entry of entries.sort()) {
    if (!entry.endsWith(SUFFIX) || entry.split(sep).includes("examples")) continue;
    const key = entry.slice(0, -SUFFIX.length).split(sep).join("/");
    schemas.set(key, JSON.parse(readFileSync(join(dir, entry), "utf8")) as JsonSchema);
  }
  return schemas;
}

export function getSchema(name: string, dir: string = DEFAULT_SCHEMA_DIR): JsonSchema {
  const schema = loadSchemas(dir).get(name);
  if (schema === undefined) {
    throw new Error(`unknown schema "${name}" in ${dir}`);
  }
  return schema;
}

export function compile(schema: JsonSchema): z.ZodType {
  return z.fromJSONSchema(schema);
}

export function validator(name: string, dir: string = DEFAULT_SCHEMA_DIR): z.ZodType {
  return compile(getSchema(name, dir));
}

export type * from "./generated/index.ts";
```

- [ ] **Step 6: Generate and run the tests**

Run: `pnpm --filter @pulseai/contracts generate && pnpm --filter @pulseai/contracts generate:check && pnpm --filter @pulseai/contracts test && pnpm --filter @pulseai/contracts typecheck`
Expected: the files under `packages/contracts/src/generated/` exist (`index.ts`, `report.ts`, `item-types/paper.ts`, …), the check exits 0, all tests pass, and typecheck is clean.

- [ ] **Step 7: Commit**

```bash
pnpm biome check --write packages/contracts biome.json
git add packages/contracts biome.json pnpm-lock.yaml
git commit -m "feat(contracts): generate TypeScript types from the JSON Schemas

json-schema-to-typescript writes one module per schema under src/generated/,
re-exported as namespaces (ReportSchema, SectionsSchema, ...). A test fails
when the generated files are stale. The schema directory is found through
the package name, so bundling the module keeps it right.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 3: `pulse site context` — one validated bundle for the site build

**Files:**
- Create: `schema/site-context.schema.json`
- Create: `packages/cli/src/pulseai/site/__init__.py`, `packages/cli/src/pulseai/site/context.py`
- Create: `examples/pulse.config.yaml`
- Create: `packages/cli/tests/test_site_context.py`
- Modify: `packages/cli/src/pulseai/cli.py` (new `site` command group), `.gitignore`
- Regenerate: `packages/cli/src/pulseai/models/site_context.py`, `packages/contracts/src/generated/`

**Interfaces:**
- Consumes: `load_config`, `load_registry`, `load_locale`, `load_schema`, `validate_document`, `check_registries`, `resolve_instance`, `exit_for`, `unusable_input_exits` (M1).
- Produces:
  - `pulseai.site.context.build_site_context(instance_dir: Path | None) -> dict[str, Any]`
  - `write_site_context(instance_dir: Path | None, out: Path) -> Path`
  - `default_context_path(instance_dir: Path | None) -> Path` (`<instance or cwd>/.pulse/site-context.json`)
  - `SiteContextError`
  - Constants `WORK_DIR = ".pulse"`, `CONTEXT_FILE = "site-context.json"`.
  - CLI `pulse site context [--instance DIR] [--out FILE]`: exit 1 on registry errors (nothing written), 2 on unusable input.
  - Context shape (`SiteContextSchema.SiteContext`): `{schema_version: 1, engine_version, config, sections (sorted by order, then id), item_types, strings, schemas}`. `schemas` maps `"report.schema.json"` and `"item-types/<file>"` to schema objects, resolved as the CLI resolves them (report schema from the engine, item-type schemas instance first).

- [ ] **Step 1: Write the failing tests**

`packages/cli/tests/test_site_context.py`:

```python
import json
from pathlib import Path

from typer.testing import CliRunner

from pulseai import __version__
from pulseai.cli import app
from pulseai.site.context import build_site_context, default_context_path

runner = CliRunner()


def _instance(tmp_path: Path, config: str) -> Path:
    instance = tmp_path / "instance"
    instance.mkdir()
    (instance / "pulse.config.yaml").write_text(config, encoding="utf-8")
    return instance


def test_context_holds_config_registries_strings_and_schemas() -> None:
    context = build_site_context()
    assert context["schema_version"] == 1
    assert context["engine_version"] == __version__
    assert context["config"]["language"] == "en"
    orders = [s["order"] for s in context["sections"]]
    assert orders == sorted(orders)
    assert {t["id"] for t in context["item_types"]} >= {"paper", "repo", "industry"}
    assert context["strings"]["sections.models"] == "Models and labs"
    assert "report.schema.json" in context["schemas"]
    assert "item-types/paper.schema.json" in context["schemas"]
    assert context["schemas"]["item-types/release.schema.json"]["title"] == "ReleaseDetail"


def test_instance_config_and_language_reach_the_context(tmp_path: Path) -> None:
    instance = _instance(tmp_path, "language: tr\ntheme:\n  preset: paper\n")
    context = build_site_context(instance)
    assert context["config"]["theme"]["preset"] == "paper"
    assert context["strings"]["sections.models"] == "Modeller ve laboratuvarlar"
    # Strings tr does not translate fall back to en.
    assert all(isinstance(value, str) for value in context["strings"].values())


def test_instance_item_type_schema_wins(tmp_path: Path, repo_root: Path) -> None:
    instance = _instance(tmp_path, "language: en\n")
    target = instance / "schema" / "item-types"
    target.mkdir(parents=True)
    schema = json.loads((repo_root / "schema/item-types/industry.schema.json").read_text())
    schema["description"] = "Instance copy"
    (target / "industry.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    context = build_site_context(instance)
    assert context["schemas"]["item-types/industry.schema.json"]["description"] == "Instance copy"


def test_cli_writes_the_default_path(tmp_path: Path) -> None:
    instance = _instance(tmp_path, "language: en\n")
    result = runner.invoke(app, ["site", "context", "--instance", str(instance)])
    assert result.exit_code == 0, result.output
    path = default_context_path(instance)
    assert path == instance / ".pulse" / "site-context.json"
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1
    assert str(path) in result.output


def test_cli_honours_out(tmp_path: Path) -> None:
    out = tmp_path / "custom" / "context.json"
    result = runner.invoke(app, ["site", "context", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert out.is_file()


def test_cli_refuses_inconsistent_registries(engine_copy: Path, tmp_path: Path) -> None:
    locale = engine_copy / "locales" / "en.json"
    doc = json.loads(locale.read_text(encoding="utf-8"))
    del doc["strings"]["sections.models"]
    locale.write_text(json.dumps(doc), encoding="utf-8")
    out = tmp_path / "context.json"
    result = runner.invoke(app, ["site", "context", "--out", str(out)])
    assert result.exit_code == 1
    assert "missing locale string 'sections.models'" in result.output
    assert not out.exists()


def test_cli_missing_report_schema_is_unusable(engine_copy: Path, tmp_path: Path) -> None:
    (engine_copy / "schema" / "report.schema.json").unlink()
    result = runner.invoke(app, ["site", "context", "--out", str(tmp_path / "c.json")])
    assert result.exit_code == 2
    assert "cannot use schema 'report.schema.json'" in result.output


def test_examples_is_a_demo_instance(repo_root: Path) -> None:
    context = build_site_context(repo_root / "examples")
    assert context["config"]["site"]["url"] == "https://mordris.github.io/PulseAI/"
```

Add the command to the exit-code contract in `packages/cli/tests/test_exit_codes.py`. Insert this entry into `COMMANDS` after `"validate"`:

```python
    "site context": (
        _args("site", "context"),
        {
            VALID: Expect(0, "stdout", "Wrote "),
            ISSUE: Expect(1, "stderr", "unknown role 'intern'"),
            BROKEN_CONFIG: Expect(2, "stderr", "schedule/time"),
            NO_ENGINE_DATA: Expect(2, "stderr", ENGINE_DATA_ENV),
            BROKEN_CATALOG: Expect(2, "stderr", "registries.yaml"),
            BROKEN_LOCALE: Expect(2, "stderr", "locales/en.json"),
            BROKEN_SECTIONS: Expect(2, "stderr", "taxonomy/sections.yaml"),
        },
    ),
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest packages/cli/tests/test_site_context.py packages/cli/tests/test_exit_codes.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'pulseai.site'`.

- [ ] **Step 3: Write the context schema**

`schema/site-context.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:pulseai:schema:site-context",
  "title": "SiteContext",
  "description": "Everything a site build needs from the engine and an instance, resolved by `pulse site context`: the effective config, the merged sections and item-types registries, locale strings with fallbacks applied, and the schemas reports are validated against. Nested documents are validated against their own schemas when the context is built.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "engine_version",
    "config",
    "sections",
    "item_types",
    "strings",
    "schemas"
  ],
  "properties": {
    "schema_version": { "const": 1 },
    "engine_version": { "type": "string", "minLength": 1 },
    "config": {
      "type": "object",
      "description": "Effective configuration (config.schema.json)."
    },
    "sections": {
      "type": "array",
      "minItems": 1,
      "description": "Merged sections registry entries (sections.schema.json), sorted by order, then id.",
      "items": { "type": "object" }
    },
    "item_types": {
      "type": "array",
      "minItems": 1,
      "description": "Merged item-types registry entries (item-types.schema.json).",
      "items": { "type": "object" }
    },
    "strings": {
      "type": "object",
      "description": "Locale strings for config.language with the fallback chain applied.",
      "propertyNames": { "pattern": "^[a-z0-9_]+(?:\\.[a-z0-9_-]+)+$" },
      "additionalProperties": { "type": "string", "minLength": 1 }
    },
    "schemas": {
      "type": "object",
      "description": "Schemas keyed by name: report.schema.json (engine) and item-types/<file> for every item type (instance first).",
      "propertyNames": { "pattern": "^(?:item-types/)?[a-z0-9_-]+\\.schema\\.json$" },
      "additionalProperties": { "type": "object" }
    }
  }
}
```

- [ ] **Step 4: Write the context builder**

`packages/cli/src/pulseai/site/__init__.py`:

```python
"""Site build support: the context bundle the Astro site reads."""
```

`packages/cli/src/pulseai/site/context.py`:

```python
"""Resolve the site build context: everything the site needs from the engine and an instance.

The merge logic for config, registries, and locales lives here (in Python) only; the site reads the
result instead of re-implementing it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pulseai import __version__
from pulseai.config import load_config
from pulseai.registry.loader import load_locale, load_registry
from pulseai.schemas import ITEM_TYPE_SCHEMA_DIR, SCHEMA_PROBLEMS, load_schema, validate_document

SITE_CONTEXT_SCHEMA = "site-context.schema.json"
REPORT_SCHEMA = "report.schema.json"
WORK_DIR = ".pulse"
CONTEXT_FILE = "site-context.json"


class SiteContextError(Exception):
    """A schema the context needs is missing or broken, or the context fails its own schema."""


def default_context_path(instance_dir: Path | None) -> Path:
    return (instance_dir or Path.cwd()) / WORK_DIR / CONTEXT_FILE


def _schemas(item_types: list[dict[str, Any]], instance_dir: Path | None) -> dict[str, Any]:
    names = sorted({f"{ITEM_TYPE_SCHEMA_DIR}/{t['schema']}" for t in item_types})
    schemas: dict[str, Any] = {}
    for name in [REPORT_SCHEMA, *names]:
        # The report schema is engine-only, exactly as `pulse validate` uses it.
        owner = None if name == REPORT_SCHEMA else instance_dir
        try:
            schemas[name] = load_schema(name, owner)
        except SCHEMA_PROBLEMS as exc:
            msg = f"cannot use schema {name!r} ({exc})"
            raise SiteContextError(msg) from None
    return schemas


def build_site_context(instance_dir: Path | None = None) -> dict[str, Any]:
    cfg = load_config(instance_dir)
    sections = sorted(
        load_registry("sections", instance_dir).data["sections"],
        key=lambda section: (section["order"], section["id"]),
    )
    item_types = load_registry("item-types", instance_dir).data["item_types"]
    context: dict[str, Any] = {
        "schema_version": 1,
        "engine_version": __version__,
        "config": cfg.model_dump(mode="json", exclude_unset=True),
        "sections": sections,
        "item_types": item_types,
        "strings": load_locale(cfg.language, instance_dir),
        "schemas": _schemas(item_types, instance_dir),
    }
    try:
        errors = validate_document(context, SITE_CONTEXT_SCHEMA)
    except SCHEMA_PROBLEMS as exc:
        msg = f"cannot use schema {SITE_CONTEXT_SCHEMA!r} ({exc})"
        raise SiteContextError(msg) from None
    if errors:
        msg = "site context is invalid\n" + "\n".join(f"  - {error}" for error in errors)
        raise SiteContextError(msg)
    return context


def write_site_context(instance_dir: Path | None, out: Path) -> Path:
    context = build_site_context(instance_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(context, ensure_ascii=False, indent=2)
    out.write_text(text + "\n", encoding="utf-8")
    return out
```

- [ ] **Step 5: Add the CLI command**

In `packages/cli/src/pulseai/cli.py`, add the import:

```python
from pulseai.site.context import SiteContextError, default_context_path, write_site_context
```

and append after the `schedule` commands:

```python
site_app = typer.Typer(help="Prepare site builds.", no_args_is_help=True)
app.add_typer(site_app, name="site")

OutOption = Annotated[
    Path | None,
    typer.Option(
        "--out",
        "-o",
        help="Where to write the context. Defaults to <instance>/.pulse/site-context.json.",
        dir_okay=False,
        resolve_path=True,
    ),
]


@site_app.command("context")
@unusable_input_exits
def site_context(instance: InstanceOption = None, out: OutOption = None) -> None:
    """Write the site build context: effective config, registries, strings, and schemas."""
    instance_dir = resolve_instance(instance)
    exit_for(check_registries(instance_dir))
    target = out or default_context_path(instance_dir)
    try:
        path = write_site_context(instance_dir, target)
    except SiteContextError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(EXIT_UNUSABLE) from None
    except OSError as exc:
        typer.echo(f"cannot write {target} ({exc.strerror or type(exc).__name__})", err=True)
        raise typer.Exit(EXIT_UNUSABLE) from None
    typer.echo(f"Wrote {path}")
```

- [ ] **Step 6: Add the demo instance and ignore build outputs**

`examples/pulse.config.yaml`:

```yaml
# Demo instance: the engine's site build, tests, and the public demo (M6) read examples/ as an
# instance directory. Reports live in examples/reports/YYYY/MM/DD/report.json.
language: en
site:
  url: https://mordris.github.io/PulseAI/
  search: true
```

Append to `.gitignore`:

```gitignore
# Site build outputs (context, generated tokens, Astro cache, built site)
.pulse/
examples/dist/
```

- [ ] **Step 7: Regenerate models and types, then run the tests**

Run: `uv run python scripts/generate_models.py && pnpm --filter @pulseai/contracts generate`
Expected: new `packages/cli/src/pulseai/models/site_context.py` and `packages/contracts/src/generated/site-context.ts`.

Run: `uv run pytest packages/cli/tests -q && pnpm --filter @pulseai/contracts test`
Expected: PASS.

Run: `uv run pulse site context --instance examples`
Expected: `Wrote …/examples/.pulse/site-context.json`.

- [ ] **Step 8: Lint and commit**

```bash
uv run ruff format . && uv run ruff check . && uv run pyright && pnpm biome check --write schema packages/contracts examples
git add schema/site-context.schema.json packages/cli packages/contracts/src/generated examples/pulse.config.yaml .gitignore
git commit -m "feat(cli): add pulse site context

Writes one validated JSON bundle with the effective config, merged sections
and item-types registries, locale strings with fallbacks, and the schemas
reports are checked against, so the site never re-implements merging.
examples/ becomes a demo instance.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 4: Sample reports in the demo instance

**Files:**
- Create: `examples/reports/2026/10/09/report.json`, `examples/reports/2026/10/10/report.json`, `examples/reports/2026/10/11/report.json`
- Create: `packages/cli/tests/test_examples.py`

**Interfaces:**
- Consumes: `validate_report_file(path, instance_dir)` (M1), `examples/pulse.config.yaml` (Task 3), the schema from Task 1.
- Produces: three sample editions (1–3) that every site test builds against. `2026-10-11` is the showcase. It has every registry item type, every visual kind (dashboard front page; vega-lite, mermaid, table and image-ref inside items, several placed in blocks), all four research groups, a reported item in `signals`, a correction, a section note, a failing source in `source_health`, an update (`update_of`), and the long-title brief `quillmark-1-8-4` used by the mobile screenshots. All entities are fictional and every URL uses IANA example domains. Images are the PulseAI logo, captioned as a sample stand-in (real images only).

- [ ] **Step 1: Write the failing test**

`packages/cli/tests/test_examples.py`:

```python
import json
from pathlib import Path
from typing import Any

import pytest

from pulseai.registry.loader import load_registry
from pulseai.report.validate import validate_report_file

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"
REPORTS = sorted((EXAMPLES / "reports").glob("*/*/*/report.json"))
VISUAL_KINDS = {"vega-lite", "mermaid", "table", "image-ref", "dashboard"}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _kinds(visual: dict[str, Any]) -> set[str]:
    kinds = {visual["kind"]}
    for tile in visual.get("tiles", []):
        if tile["tile"] == "visual":
            kinds |= _kinds(tile["visual"])
    return kinds


def test_three_sample_editions() -> None:
    dates = ["/".join(p.parts[-4:-1]) for p in REPORTS]
    assert dates == ["2026/10/09", "2026/10/10", "2026/10/11"]


@pytest.mark.parametrize("path", REPORTS, ids=lambda p: "/".join(p.parts[-4:-1]))
def test_sample_report_is_valid_without_warnings(path: Path) -> None:
    issues = validate_report_file(path, EXAMPLES)
    assert [f"{i.level} {i.where}: {i.message}" for i in issues] == []


@pytest.mark.parametrize("path", REPORTS, ids=lambda p: "/".join(p.parts[-4:-1]))
def test_path_matches_the_report_date(path: Path) -> None:
    report = _load(path)
    assert report["meta"]["date"] == "-".join(path.parts[-4:-1])
    assert report["meta"]["sample"] is True


def test_editions_count_up_by_date() -> None:
    assert [_load(p)["meta"]["edition"] for p in REPORTS] == [1, 2, 3]


def test_showcase_covers_every_item_type_and_visual_kind() -> None:
    showcase = _load(REPORTS[-1])
    registry_types = {t["id"] for t in load_registry("item-types", EXAMPLES).data["item_types"]}
    used_types = {item["type"] for item in showcase["items"]}
    assert used_types == registry_types
    kinds: set[str] = set()
    for visual in showcase["front_page"]:
        kinds |= _kinds(visual)
    for item in showcase["items"]:
        for visual in item["visuals"]:
            kinds |= _kinds(visual)
    assert kinds == VISUAL_KINDS
    assert any("block" in v for item in showcase["items"] for v in item["visuals"])
    assert showcase["signals"] and showcase["corrections"] and showcase["section_notes"]
    assert any(not source["ok"] for source in showcase["meta"]["source_health"])
    assert any("update_of" in item for item in showcase["items"])
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest packages/cli/tests/test_examples.py -q`
Expected: FAIL (`test_three_sample_editions` gets `[]`).

- [ ] **Step 3: Write edition 1 (2026-10-09)**

`examples/reports/2026/10/09/report.json`:

```json
{
  "schema_version": 1,
  "meta": {
    "date": "2026-10-09",
    "edition": 1,
    "window": { "start": "2026-10-08T14:00:00Z", "end": "2026-10-09T14:00:00Z", "tz": "Europe/Istanbul" },
    "language": "en",
    "engine_version": "0.1.0",
    "host": "fixture",
    "models": { "editor": "claude-opus-5-5", "section-researcher": "claude-sonnet-5-5" },
    "stats": { "scanned": 214, "triaged": 22, "verified": 5, "published": 3 },
    "cost_usd": 4.12,
    "source_health": [
      { "source_id": "hf-daily-papers", "ok": true, "items": 38 },
      { "source_id": "claude-code-releases", "ok": true, "items": 1 }
    ],
    "sample": true,
    "mode": "normal"
  },
  "headline": "Northwind cuts Atlas-2.5 prices as Lumen SDK adds streaming tools",
  "pulse_score": { "value": 10, "avg_7d": null },
  "kpis": [
    { "label": "Items published", "value": 3 },
    { "label": "Papers read in full", "value": 2 }
  ],
  "tldr": [
    { "text": "Atlas-2.5 input tokens now cost 40% less.", "item_id": "northwind-atlas-2-5-price-cut" },
    { "text": "Lumen Agent SDK 2.3 streams tool calls.", "item_id": "lumen-sdk-2-3" }
  ],
  "featured": { "paper_of_the_day": "self-check-agents" },
  "front_page": [],
  "items": [
    {
      "id": "northwind-atlas-2-5-price-cut",
      "section": "models",
      "type": "model_release",
      "title": "Northwind Labs cuts Atlas-2.5 prices by 40%",
      "entity_key": "northwind/atlas-2.5",
      "thread_id": "northwind-atlas",
      "impact": 4,
      "novelty": 3,
      "relevance": 4,
      "confidence": "confirmed",
      "summary": "Northwind Labs lowered Atlas-2.5 input pricing from $5 to $3 per million tokens; output pricing is unchanged.",
      "why_it_matters": "Long-context agent runs on Atlas-2.5 get noticeably cheaper without changing models.",
      "what_to_do": "Re-run your cost estimates for agent workloads that read large repositories.",
      "sources": [
        { "url": "https://example.org/northwind/pricing", "title": "Northwind pricing page", "tier": "T1", "kind": "primary", "fetched_at": "2026-10-09T12:10:00Z" }
      ],
      "facts": [
        { "label": "Input price", "value": 3, "unit": "USD/Mtok", "source_ref": 0, "quote": "Input: $3.00 per million tokens" }
      ],
      "visuals": [
        {
          "kind": "vega-lite",
          "id": "atlas-2-5-price",
          "title": "Atlas-2.5 input price per million tokens",
          "alt": "Bar chart: input price fell from 5 to 3 US dollars per million tokens",
          "source_note": "Northwind pricing page",
          "block": "price_comparison",
          "spec": {
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "data": { "values": [ { "period": "Before", "usd": 5 }, { "period": "After", "usd": 3 } ] },
            "mark": { "type": "bar" },
            "encoding": {
              "x": { "field": "period", "type": "nominal", "sort": null, "title": null },
              "y": { "field": "usd", "type": "quantitative", "title": "USD per million input tokens" }
            }
          }
        }
      ],
      "images": [],
      "detail": {
        "org": "Northwind Labs",
        "model": "Atlas-2.5",
        "context_tokens": 400000,
        "price_in_per_mtok": 3,
        "price_out_per_mtok": 15,
        "modalities": ["text", "image"],
        "availability": ["API"],
        "weights": "closed",
        "license": "Proprietary"
      }
    },
    {
      "id": "lumen-sdk-2-3",
      "section": "tooling",
      "type": "framework_release",
      "title": "Lumen Agent SDK 2.3 streams tool calls",
      "entity_key": "lumen/agent-sdk",
      "thread_id": "lumen-agent-sdk",
      "impact": 3,
      "novelty": 3,
      "relevance": 5,
      "confidence": "confirmed",
      "summary": "Lumen Agent SDK 2.3 streams partial tool-call arguments and adds cancellation tokens.",
      "why_it_matters": "Agents can show tool progress in the UI before a call completes.",
      "sources": [
        { "url": "https://example.org/lumen/releases/2.3.0", "title": "Lumen Agent SDK 2.3.0 release notes", "tier": "T1", "kind": "primary" }
      ],
      "facts": [],
      "visuals": [],
      "images": [],
      "detail": {
        "product": "Lumen Agent SDK",
        "version": "2.3.0",
        "previous_version": "2.2.4",
        "changelog": [
          { "tag": "new", "text": "Streaming tool-call arguments." },
          { "tag": "new", "text": "Cancellation tokens for long-running tools." },
          { "tag": "fix", "text": "Retries no longer duplicate tool results." }
        ],
        "verdict": "trial",
        "snippet": "npm install @lumen/agent-sdk@2.3.0"
      }
    },
    {
      "id": "self-check-agents",
      "section": "research",
      "type": "paper",
      "title": "Self-check prompts reduce silent tool failures in agents",
      "entity_key": "paper/self-check-agents",
      "impact": 3,
      "novelty": 3,
      "relevance": 4,
      "confidence": "confirmed",
      "summary": "Asking an agent to restate each tool result before continuing caught most silent tool failures in a benchmark of 400 tasks.",
      "why_it_matters": "A one-line prompt change that makes agent failures visible instead of silent.",
      "sources": [
        { "url": "https://example.org/papers/self-check-agents", "title": "Self-check prompts (preprint)", "tier": "T1", "kind": "primary" }
      ],
      "facts": [
        { "label": "Tasks", "value": 400, "source_ref": 0, "quote": "a benchmark of 400 multi-step tasks" }
      ],
      "visuals": [],
      "images": [],
      "detail": {
        "peer_reviewed": false,
        "authors": ["R. Okafor", "L. Brandt"],
        "affiliations": ["Example University"],
        "tldr": "Making agents restate tool results surfaces silent failures.",
        "plain_explanation": "After each tool call the agent writes one sentence about what the tool returned, which exposes empty or failed results.",
        "problem": "Agents often continue after a tool silently returns nothing.",
        "key_idea": "Force an explicit restatement of every tool result.",
        "method_steps": ["Add a restatement step after each tool call", "Flag restatements that contradict the plan"],
        "critical_review": ["Single benchmark", "No cost analysis"],
        "reproducibility": { "code_url": "https://example.org/code/self-check" },
        "takeaway": "Cheap to try in any agent loop.",
        "reading_guide": {
          "sections": ["Section 2", "Table 1"],
          "glossary": { "Silent failure": "A tool call that fails without raising an error" },
          "reading_minutes": 15,
          "difficulty": "intro"
        }
      }
    }
  ],
  "adoption_radar": [
    { "item_id": "lumen-sdk-2-3", "ring": "trial", "rationale": "Streaming tools are useful, but the API is marked beta." }
  ],
  "action_list": [
    { "text": "Re-run cost estimates for long-context agent runs.", "item_id": "northwind-atlas-2-5-price-cut" }
  ],
  "signals": [],
  "corrections": [],
  "section_notes": {},
  "methodology": {
    "notes": ["Sample edition written by hand for the demo site; every entity is fictional."],
    "rejected": []
  }
}
```

- [ ] **Step 4: Write edition 2 (2026-10-10)**

`examples/reports/2026/10/10/report.json`:

```json
{
  "schema_version": 1,
  "meta": {
    "date": "2026-10-10",
    "edition": 2,
    "window": { "start": "2026-10-09T14:00:00Z", "end": "2026-10-10T14:00:00Z", "tz": "Europe/Istanbul" },
    "language": "en",
    "engine_version": "0.1.0",
    "host": "fixture",
    "models": { "editor": "claude-opus-5-5", "section-researcher": "claude-sonnet-5-5" },
    "stats": { "scanned": 238, "triaged": 25, "verified": 6, "published": 4 },
    "cost_usd": 4.87,
    "source_health": [
      { "source_id": "hf-daily-papers", "ok": true, "items": 41 },
      { "source_id": "claude-code-releases", "ok": true, "items": 0 }
    ],
    "sample": true,
    "mode": "normal"
  },
  "headline": "Relay CLI 3.0 enters release candidate as GPU rental prices slide",
  "pulse_score": { "value": 13, "avg_7d": 10 },
  "kpis": [
    { "label": "Items published", "value": 4, "delta": 1, "series": [3, 4] },
    { "label": "Papers read in full", "value": 3, "delta": 1, "series": [2, 3] }
  ],
  "tldr": [
    { "text": "Relay CLI 3.0 RC adds parallel subagents.", "item_id": "relay-cli-3-rc" },
    { "text": "Hourly GPU rental prices fell for the third month.", "item_id": "example-gpu-pricing" }
  ],
  "featured": { "paper_of_the_day": "budget-aware-planning" },
  "front_page": [],
  "items": [
    {
      "id": "relay-cli-3-rc",
      "section": "tooling",
      "type": "tool_release",
      "title": "Relay CLI 3.0 release candidate adds parallel subagents",
      "entity_key": "relay/cli",
      "thread_id": "relay-cli",
      "impact": 3,
      "novelty": 4,
      "relevance": 5,
      "confidence": "confirmed",
      "summary": "The first Relay CLI 3.0 release candidate runs up to eight subagents in parallel and introduces a plugin manifest.",
      "why_it_matters": "Parallel subagents cut wall-clock time for repository-wide refactors.",
      "caveats": "Release candidate: the plugin manifest format may still change before 3.0.",
      "sources": [
        { "url": "https://example.org/relay/releases/3.0.0-rc.1", "title": "Relay CLI 3.0.0-rc.1", "tier": "T1", "kind": "primary" }
      ],
      "facts": [
        { "label": "Parallel subagents", "value": 8, "source_ref": 0, "quote": "up to eight subagents in parallel" }
      ],
      "visuals": [],
      "images": [],
      "detail": {
        "product": "Relay CLI",
        "version": "3.0.0-rc.1",
        "previous_version": "2.9.2",
        "changelog": [
          { "tag": "new", "text": "Parallel subagents (up to eight)." },
          { "tag": "new", "text": "Plugin manifest, version 1." },
          { "tag": "breaking", "text": "The --agents flag is renamed to --subagents." }
        ],
        "verdict": "assess"
      }
    },
    {
      "id": "example-gpu-pricing",
      "section": "models",
      "type": "industry",
      "title": "Hourly GPU rental prices fall for a third month",
      "entity_key": "industry/gpu-rental-prices",
      "impact": 3,
      "novelty": 2,
      "relevance": 3,
      "confidence": "confirmed",
      "summary": "The Example Compute Index shows on-demand accelerator prices down 6% month over month.",
      "why_it_matters": "Self-hosting open-weights models keeps getting cheaper.",
      "sources": [
        { "url": "https://example.com/compute-index/2026-10", "title": "Example Compute Index, October 2026", "tier": "T1-data", "kind": "primary" }
      ],
      "facts": [
        { "label": "Monthly change", "value": -6, "unit": "%", "source_ref": 0, "quote": "down 6% month over month" }
      ],
      "visuals": [
        {
          "kind": "vega-lite",
          "id": "gpu-price-trend",
          "title": "On-demand accelerator price index",
          "alt": "Line chart: the price index fell from 100 in July to 82 in October",
          "source_note": "Example Compute Index",
          "block": "timeline",
          "spec": {
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "data": { "values": [ { "month": "2026-07", "index": 100 }, { "month": "2026-08", "index": 93 }, { "month": "2026-09", "index": 87 }, { "month": "2026-10", "index": 82 } ] },
            "mark": { "type": "line", "point": true },
            "encoding": {
              "x": { "field": "month", "type": "temporal", "timeUnit": "yearmonth", "title": null },
              "y": { "field": "index", "type": "quantitative", "title": "Index (July = 100)", "scale": { "zero": false } }
            }
          }
        }
      ],
      "images": [],
      "detail": {
        "who": "Example Compute Index",
        "what": "On-demand accelerator prices fell 6% month over month",
        "builder_impact": "Re-check self-hosting break-even points for open-weights models."
      }
    },
    {
      "id": "budget-aware-planning",
      "section": "research",
      "type": "paper",
      "title": "Budget-aware planning keeps agents under a token limit",
      "entity_key": "paper/budget-aware-planning",
      "impact": 4,
      "novelty": 4,
      "relevance": 4,
      "confidence": "confirmed",
      "summary": "A planner that tracks the remaining token budget finished 91% of tasks within budget, against 64% for an unbudgeted baseline.",
      "why_it_matters": "Hard budgets are a common production requirement for agents.",
      "sources": [
        { "url": "https://example.org/papers/budget-aware-planning", "title": "Budget-aware planning (preprint)", "tier": "T1", "kind": "primary" }
      ],
      "facts": [
        { "label": "Tasks within budget", "value": 91, "unit": "%", "source_ref": 0, "quote": "91% of tasks within budget" }
      ],
      "visuals": [],
      "images": [],
      "detail": {
        "peer_reviewed": false,
        "authors": ["M. Haddad", "J. Lindqvist", "S. Mori"],
        "tldr": "Planning with an explicit budget keeps agents under token limits.",
        "plain_explanation": "The planner knows how many tokens are left and picks cheaper steps as the budget runs low.",
        "problem": "Agents overshoot token budgets on long tasks.",
        "key_idea": "Make the remaining budget part of the planner's state.",
        "method_steps": ["Estimate the cost of each candidate step", "Prefer steps that fit the remaining budget", "Re-plan when the estimate is wrong"],
        "critical_review": ["Cost estimates come from the same model being evaluated"],
        "reproducibility": {},
        "takeaway": "Expose the remaining budget to the planner, not only to the orchestrator.",
        "reading_guide": {
          "sections": ["Section 3", "Figure 2"],
          "glossary": { "Budget": "The maximum number of tokens a task may use" },
          "reading_minutes": 25,
          "difficulty": "intermediate"
        }
      }
    },
    {
      "id": "agent-trace-viewer",
      "section": "oss",
      "type": "repo",
      "title": "agent-trace-viewer: a local UI for agent traces",
      "entity_key": "repo/example-org/agent-trace-viewer",
      "impact": 3,
      "novelty": 3,
      "relevance": 4,
      "confidence": "confirmed",
      "summary": "An MIT-licensed local web UI that renders OpenTelemetry agent traces as a timeline.",
      "why_it_matters": "Debugging agents is easier when every tool call is on one timeline.",
      "sources": [
        { "url": "https://example.org/example-org/agent-trace-viewer", "title": "agent-trace-viewer repository", "tier": "T1", "kind": "primary" }
      ],
      "facts": [],
      "visuals": [],
      "images": [],
      "detail": {
        "full_name": "example-org/agent-trace-viewer",
        "language": "TypeScript",
        "license": "MIT",
        "stars": 2140,
        "stars_delta_7d": 1350,
        "last_commit": "2026-10-10",
        "alternatives": ["Example Trace Explorer"],
        "quickstart": "npx agent-trace-viewer ./traces"
      }
    }
  ],
  "adoption_radar": [
    { "item_id": "relay-cli-3-rc", "ring": "assess", "rationale": "Wait for the final 3.0 release before switching team workflows." }
  ],
  "action_list": [
    { "text": "Try agent-trace-viewer on one failing agent run.", "item_id": "agent-trace-viewer" }
  ],
  "signals": [],
  "corrections": [],
  "section_notes": {},
  "methodology": {
    "notes": ["Sample edition written by hand for the demo site; every entity is fictional."],
    "rejected": [
      { "title": "Unverified benchmark thread", "reason": "No primary source", "url": "https://example.net/thread/1" }
    ]
  }
}
```

- [ ] **Step 5: Write edition 3, the showcase (2026-10-11)**

`examples/reports/2026/10/11/report.json`:

```json
{
  "schema_version": 1,
  "meta": {
    "date": "2026-10-11",
    "edition": 3,
    "window": { "start": "2026-10-10T14:00:00Z", "end": "2026-10-11T14:00:00Z", "tz": "Europe/Istanbul" },
    "language": "en",
    "engine_version": "0.1.0",
    "host": "fixture",
    "models": {
      "editor": "claude-opus-5-5",
      "paper-analyst": "claude-opus-5-5",
      "section-researcher": "claude-sonnet-5-5",
      "paper-triage": "claude-haiku-5-5"
    },
    "stats": { "scanned": 412, "triaged": 37, "verified": 16, "published": 13 },
    "cost_usd": 6.31,
    "source_health": [
      { "source_id": "hf-daily-papers", "ok": true, "items": 46 },
      { "source_id": "claude-code-releases", "ok": true, "items": 1 },
      { "source_id": "openrouter-models", "ok": true, "items": 3 },
      { "source_id": "example-lab-blog", "ok": false, "items": 0, "error": "HTTP 503 after 3 retries" }
    ],
    "sample": true,
    "mode": "normal"
  },
  "headline": "Atlas-3 arrives with a million-token context as Relay CLI 3.0 ships",
  "pulse_score": { "value": 45, "avg_7d": 11.5 },
  "kpis": [
    { "label": "Items published", "value": 13, "delta": 9, "series": [3, 4, 13] },
    { "label": "Papers read in full", "value": 6, "delta": 3, "series": [2, 3, 6] },
    { "label": "Releases tracked", "value": 5, "delta": 4, "series": [1, 1, 5] },
    { "label": "Security advisories", "value": 1, "delta": 1, "series": [0, 0, 1] }
  ],
  "tldr": [
    { "text": "Northwind's Atlas-3 reads a million tokens at half Atlas-2.5's output price.", "item_id": "northwind-atlas-3" },
    { "text": "Relay CLI 3.0 is final: parallel subagents and a stable plugin API.", "item_id": "relay-cli-3-0" },
    { "text": "Critic-guided search lets small models beat larger ones on long agent tasks.", "item_id": "verify-then-expand" },
    { "text": "Upgrade pyfetchkit now: a critical path traversal is fixed in 4.2.1.", "item_id": "pyfetchkit-path-traversal" }
  ],
  "featured": { "paper_of_the_day": "verify-then-expand" },
  "front_page": [
    {
      "kind": "dashboard",
      "id": "today-at-a-glance",
      "title": "Today at a glance",
      "alt": "Dashboard with three headline numbers, impact by section, and the highest-impact items",
      "source_note": "This report",
      "columns": 3,
      "tiles": [
        { "tile": "stat", "label": "Items published", "value": 13, "delta": 9, "series": [3, 4, 13] },
        { "tile": "stat", "label": "Highest impact", "value": "5 / 5" },
        { "tile": "stat", "label": "Lowest model price", "value": 2.5, "unit": "USD/Mtok" },
        {
          "tile": "visual",
          "span": 2,
          "visual": {
            "kind": "vega-lite",
            "id": "impact-by-section",
            "title": "Total impact by section",
            "alt": "Bar chart: models 11, tooling 12, research 14, software and OSS 8",
            "source_note": "Impact scores in this report",
            "spec": {
              "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
              "data": { "values": [ { "section": "Models", "impact": 11 }, { "section": "Tooling", "impact": 12 }, { "section": "Research", "impact": 14 }, { "section": "Software and OSS", "impact": 8 } ] },
              "mark": { "type": "bar" },
              "encoding": {
                "y": { "field": "section", "type": "nominal", "sort": "-x", "title": null },
                "x": { "field": "impact", "type": "quantitative", "title": "Sum of impact scores" }
              }
            }
          }
        },
        {
          "tile": "visual",
          "visual": {
            "kind": "table",
            "id": "top-items",
            "title": "Highest impact",
            "alt": "Table of the three items with impact 5",
            "source_note": "This report",
            "columns": ["Item", "Impact"],
            "rows": [["Atlas-3", 5], ["Verify-then-expand", 5], ["pyfetchkit advisory", 5]]
          }
        }
      ]
    }
  ],
  "items": [
    {
      "id": "northwind-atlas-3",
      "section": "models",
      "type": "model_release",
      "title": "Northwind Labs releases Atlas-3 with a one-million-token context",
      "entity_key": "northwind/atlas-3",
      "thread_id": "northwind-atlas",
      "impact": 5,
      "novelty": 5,
      "relevance": 5,
      "confidence": "confirmed",
      "summary": "Atlas-3 accepts one million tokens of context, adds audio input, and lowers output pricing to $10 per million tokens.",
      "why_it_matters": "Whole-repository agent runs fit in one context without retrieval, at a lower price than Atlas-2.5.",
      "what_to_do": "Benchmark Atlas-3 on your longest agent task before changing defaults.",
      "caveats": "The million-token tier is limited to the API; the chat app is capped at 200,000 tokens.",
      "sources": [
        { "url": "https://example.org/northwind/atlas-3", "title": "Introducing Atlas-3", "tier": "T1", "kind": "primary", "fetched_at": "2026-10-11T11:02:00Z" },
        { "url": "https://example.org/northwind/atlas-3/model-card", "title": "Atlas-3 model card", "tier": "T1", "kind": "primary", "fetched_at": "2026-10-11T11:04:00Z" },
        { "url": "https://example.net/newsletter/atlas-3", "title": "Example Newsletter on Atlas-3", "tier": "T2", "kind": "secondary" }
      ],
      "facts": [
        { "label": "Context window", "value": 1000000, "unit": "tokens", "source_ref": 0, "quote": "a context window of one million tokens" },
        { "label": "Output price", "value": 10, "unit": "USD/Mtok", "source_ref": 0, "quote": "$10 per million output tokens" },
        { "label": "CodeTasks-500 score", "value": 71.2, "unit": "%", "source_ref": 1, "quote": "CodeTasks-500: 71.2%" }
      ],
      "visuals": [
        {
          "kind": "vega-lite",
          "id": "atlas-3-benchmarks",
          "title": "CodeTasks-500 success rate",
          "alt": "Bar chart: Atlas-3 71.2%, Atlas-2.5 58.4%, previous best open model 54.9%",
          "source_note": "Atlas-3 model card",
          "block": "benchmarks",
          "spec": {
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "data": { "values": [ { "model": "Atlas-3", "score": 71.2 }, { "model": "Atlas-2.5", "score": 58.4 }, { "model": "Best open model", "score": 54.9 } ] },
            "mark": { "type": "bar" },
            "encoding": {
              "x": { "field": "model", "type": "nominal", "sort": "-y", "title": null },
              "y": { "field": "score", "type": "quantitative", "title": "Tasks solved (%)", "scale": { "domain": [0, 100] } }
            }
          }
        },
        {
          "kind": "vega-lite",
          "id": "atlas-price-comparison",
          "title": "Price per million tokens",
          "alt": "Grouped bar chart comparing input and output prices of Atlas-3 and Atlas-2.5",
          "source_note": "Northwind pricing page",
          "block": "price_comparison",
          "spec": {
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "data": { "values": [ { "model": "Atlas-3", "kind": "Input", "usd": 2.5 }, { "model": "Atlas-3", "kind": "Output", "usd": 10 }, { "model": "Atlas-2.5", "kind": "Input", "usd": 3 }, { "model": "Atlas-2.5", "kind": "Output", "usd": 15 } ] },
            "mark": { "type": "bar" },
            "encoding": {
              "x": { "field": "kind", "type": "nominal", "title": null },
              "xOffset": { "field": "model" },
              "y": { "field": "usd", "type": "quantitative", "title": "USD per million tokens" },
              "color": { "field": "model", "type": "nominal", "title": "Model" }
            }
          }
        }
      ],
      "images": [
        {
          "url": "https://raw.githubusercontent.com/Mordris/PulseAI/main/docs/assets/logo-light.svg",
          "caption": "Sample image: the PulseAI logo stands in for a launch screenshot in this sample edition",
          "credit": "PulseAI",
          "alt": "PulseAI logo",
          "license": "MIT"
        }
      ],
      "detail": {
        "org": "Northwind Labs",
        "model": "Atlas-3",
        "context_tokens": 1000000,
        "price_in_per_mtok": 2.5,
        "price_out_per_mtok": 10,
        "modalities": ["text", "image", "audio"],
        "availability": ["API", "Chat app"],
        "weights": "closed",
        "license": "Proprietary",
        "try_it": "Call the model id atlas-3 from the Northwind API, or pick Atlas-3 in the chat app."
      }
    },
    {
      "id": "example-co-inference-cloud",
      "section": "models",
      "type": "industry",
      "title": "Example Co opens an inference cloud in three regions",
      "entity_key": "example-co/inference-cloud",
      "impact": 3,
      "novelty": 3,
      "relevance": 3,
      "confidence": "confirmed",
      "summary": "Example Co launched a hosted inference service for open-weights models in the EU, the US, and APAC.",
      "why_it_matters": "Another hosting option with EU data residency for open-weights models.",
      "sources": [
        { "url": "https://example.com/news/inference-cloud", "title": "Example Co announcement", "tier": "T1", "kind": "primary" }
      ],
      "facts": [
        { "label": "Regions", "value": 3, "source_ref": 0, "quote": "available in three regions" }
      ],
      "visuals": [
        {
          "kind": "table",
          "id": "inference-cloud-regions",
          "title": "Launch regions",
          "alt": "Table listing the three launch regions and their status",
          "source_note": "Example Co announcement",
          "block": "summary_facts",
          "columns": ["Region", "Status", "Data residency"],
          "rows": [["EU", "Available", true], ["US", "Available", false], ["APAC", "Preview", false]]
        },
        {
          "kind": "vega-lite",
          "id": "inference-cloud-timeline",
          "title": "From announcement to general availability",
          "alt": "Timeline with three milestones from June to October 2026",
          "source_note": "Example Co announcements",
          "block": "timeline",
          "spec": {
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "data": { "values": [ { "date": "2026-06-02", "event": "Announced" }, { "date": "2026-08-18", "event": "Private preview" }, { "date": "2026-10-11", "event": "Generally available" } ] },
            "layer": [
              { "mark": { "type": "rule" }, "encoding": { "x": { "field": "date", "type": "temporal", "aggregate": "min" }, "x2": { "field": "date", "aggregate": "max" } } },
              { "mark": { "type": "point", "filled": true, "size": 120 }, "encoding": { "x": { "field": "date", "type": "temporal", "title": null } } },
              { "mark": { "type": "text", "dy": -14 }, "encoding": { "x": { "field": "date", "type": "temporal" }, "text": { "field": "event" } } }
            ]
          }
        }
      ],
      "images": [],
      "detail": {
        "who": "Example Co",
        "what": "Launched a hosted inference cloud for open-weights models",
        "amount": "Three regions at launch",
        "builder_impact": "Teams that need EU data residency get another managed option."
      }
    },
    {
      "id": "open-agents-leaderboard",
      "section": "models",
      "type": "leaderboard_shift",
      "title": "Atlas-3 takes first place on the Open Agents Leaderboard",
      "entity_key": "leaderboard/open-agents",
      "impact": 3,
      "novelty": 3,
      "relevance": 4,
      "confidence": "confirmed",
      "summary": "Atlas-3 entered the Open Agents Leaderboard at first place, moving Atlas-2.5 to third.",
      "why_it_matters": "Independent confirmation of the vendor's benchmark claims.",
      "sources": [
        { "url": "https://example.org/leaderboards/open-agents", "title": "Open Agents Leaderboard", "tier": "T1-data", "kind": "primary" }
      ],
      "facts": [],
      "visuals": [],
      "images": [],
      "detail": {
        "board": "Open Agents Leaderboard",
        "movers": [
          { "name": "Atlas-3", "after": 1 },
          { "name": "Example Pro 2", "before": 1, "after": 2 },
          { "name": "Atlas-2.5", "before": 2, "after": 3 },
          { "name": "Open Model 70B", "before": 3, "after": 4 }
        ],
        "reliability_note": "Scores are self-reported by submitters and spot-checked by the maintainers."
      }
    },
    {
      "id": "relay-cli-3-0",
      "section": "tooling",
      "type": "tool_release",
      "title": "Relay CLI 3.0 ships parallel subagents and a stable plugin API",
      "entity_key": "relay/cli",
      "thread_id": "relay-cli",
      "update_of": "2026-10-10#relay-cli-3-rc",
      "impact": 4,
      "novelty": 4,
      "relevance": 5,
      "confidence": "confirmed",
      "summary": "Relay CLI 3.0 is final: up to eight parallel subagents, plugin manifest version 1, and 30% faster cold starts.",
      "why_it_matters": "Parallel subagents and plugins make Relay a credible team-wide agent runner.",
      "what_to_do": "Rename --agents to --subagents in scripts before upgrading.",
      "sources": [
        { "url": "https://example.org/relay/releases/3.0.0", "title": "Relay CLI 3.0.0", "tier": "T1", "kind": "primary" }
      ],
      "facts": [
        { "label": "Cold start", "value": -30, "unit": "%", "source_ref": 0, "quote": "cold starts are 30% faster" }
      ],
      "visuals": [
        {
          "kind": "vega-lite",
          "id": "relay-release-cadence",
          "title": "Relay CLI releases per month",
          "alt": "Bar chart of releases per month from May to October 2026, between 2 and 6 a month",
          "source_note": "Relay CLI releases page",
          "block": "cadence",
          "spec": {
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "data": { "values": [ { "month": "2026-05", "releases": 3 }, { "month": "2026-06", "releases": 2 }, { "month": "2026-07", "releases": 4 }, { "month": "2026-08", "releases": 5 }, { "month": "2026-09", "releases": 6 }, { "month": "2026-10", "releases": 2 } ] },
            "mark": { "type": "bar" },
            "encoding": {
              "x": { "field": "month", "type": "ordinal", "timeUnit": "yearmonth", "title": null },
              "y": { "field": "releases", "type": "quantitative", "title": "Releases" }
            }
          }
        }
      ],
      "images": [],
      "detail": {
        "product": "Relay CLI",
        "version": "3.0.0",
        "previous_version": "2.9.2",
        "changelog": [
          { "tag": "new", "text": "Parallel subagents, up to eight per session." },
          { "tag": "new", "text": "Plugin manifest version 1 is stable." },
          { "tag": "perf", "text": "Cold starts are 30% faster." },
          { "tag": "breaking", "text": "The --agents flag is renamed to --subagents." },
          { "tag": "fix", "text": "Interrupted sessions resume without losing tool output." },
          { "tag": "security", "text": "Plugins run with a read-only file system unless granted write access." },
          { "tag": "deprecation", "text": "The v0 plugin format is deprecated and will be removed in 3.2." }
        ],
        "verdict": "trial",
        "snippet": "npm install -g relay-cli@3\nrelay --subagents 4 \"migrate the test suite to Vitest\"",
        "migration_notes": "Replace --agents with --subagents. v0 plugins keep working until 3.2; convert them with relay plugin migrate."
      }
    },
    {
      "id": "lumen-sdk-2-4",
      "section": "tooling",
      "type": "framework_release",
      "title": "Lumen Agent SDK 2.4 adds typed tool schemas",
      "entity_key": "lumen/agent-sdk",
      "thread_id": "lumen-agent-sdk",
      "impact": 3,
      "novelty": 3,
      "relevance": 5,
      "confidence": "confirmed",
      "summary": "Lumen Agent SDK 2.4 generates tool schemas from TypeScript types and validates tool results at runtime.",
      "why_it_matters": "Typed tools remove a whole class of malformed tool-call bugs.",
      "sources": [
        { "url": "https://example.org/lumen/releases/2.4.0", "title": "Lumen Agent SDK 2.4.0 release notes", "tier": "T1", "kind": "primary" }
      ],
      "facts": [],
      "visuals": [],
      "images": [],
      "detail": {
        "product": "Lumen Agent SDK",
        "version": "2.4.0",
        "previous_version": "2.3.0",
        "changelog": [
          { "tag": "new", "text": "Tool schemas generated from TypeScript types." },
          { "tag": "new", "text": "Runtime validation of tool results." }
        ],
        "verdict": "adopt",
        "snippet": "npm install @lumen/agent-sdk@2.4.0"
      }
    },
    {
      "id": "mcp-inspector-plus",
      "section": "tooling",
      "type": "repo",
      "title": "mcp-inspector-plus gains 4,200 stars in a week",
      "entity_key": "repo/example-org/mcp-inspector-plus",
      "impact": 3,
      "novelty": 3,
      "relevance": 5,
      "confidence": "confirmed",
      "summary": "A desktop inspector for MCP servers that records sessions and replays tool calls against a new server version.",
      "why_it_matters": "Replaying recorded sessions makes MCP server upgrades testable.",
      "sources": [
        { "url": "https://example.org/example-org/mcp-inspector-plus", "title": "mcp-inspector-plus repository", "tier": "T1", "kind": "primary" }
      ],
      "facts": [
        { "label": "Stars this week", "value": 4200, "source_ref": 0, "quote": "4.2k stars" }
      ],
      "visuals": [
        {
          "kind": "vega-lite",
          "id": "mcp-inspector-stars",
          "title": "GitHub stars, last 7 days",
          "alt": "Line chart: stars rose from 1,100 to 5,300 over seven days",
          "source_note": "Repository star history",
          "block": "stars_trend",
          "spec": {
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "data": { "values": [ { "day": "2026-10-05", "stars": 1100 }, { "day": "2026-10-06", "stars": 1250 }, { "day": "2026-10-07", "stars": 1900 }, { "day": "2026-10-08", "stars": 2800 }, { "day": "2026-10-09", "stars": 3600 }, { "day": "2026-10-10", "stars": 4700 }, { "day": "2026-10-11", "stars": 5300 } ] },
            "mark": { "type": "line", "point": true },
            "encoding": {
              "x": { "field": "day", "type": "temporal", "title": null },
              "y": { "field": "stars", "type": "quantitative", "title": "Stars" }
            }
          }
        }
      ],
      "images": [],
      "detail": {
        "full_name": "example-org/mcp-inspector-plus",
        "language": "Rust",
        "license": "Apache-2.0",
        "stars": 5300,
        "stars_delta_7d": 4200,
        "last_commit": "2026-10-11",
        "alternatives": ["Example MCP Inspector", "mcp-cli-debug"],
        "quickstart": "cargo install mcp-inspector-plus\nmcp-inspector-plus record -- node ./server.js"
      }
    },
    {
      "id": "quillmark-1-8-4",
      "section": "tooling",
      "type": "tool_release",
      "title": "Quillmark 1.8.4, the documentation generator, fixes a rare crash when a very long nested table of contents contains Unicode headings",
      "entity_key": "quillmark/quillmark",
      "impact": 2,
      "novelty": 1,
      "relevance": 2,
      "confidence": "confirmed",
      "summary": "A patch release that fixes a crash in table-of-contents generation.",
      "why_it_matters": "Only affects sites with deeply nested Unicode headings.",
      "sources": [
        { "url": "https://example.org/quillmark/releases/1.8.4", "title": "Quillmark 1.8.4", "tier": "T1", "kind": "primary" }
      ],
      "facts": [],
      "visuals": [],
      "images": [],
      "detail": {
        "product": "Quillmark",
        "version": "1.8.4",
        "previous_version": "1.8.3",
        "changelog": [{ "tag": "fix", "text": "No crash on deeply nested Unicode headings." }],
        "verdict": "adopt"
      }
    },
    {
      "id": "verify-then-expand",
      "section": "research",
      "type": "paper",
      "title": "Verify-then-expand: critic-guided search for long-horizon agents",
      "entity_key": "paper/verify-then-expand",
      "impact": 5,
      "novelty": 5,
      "relevance": 5,
      "confidence": "confirmed",
      "summary": "A small model that scores candidate plans with a critic and expands only the best branches solved more long-horizon tasks than a model four times its size.",
      "why_it_matters": "Spending inference compute on verification can beat buying a bigger model for agent workloads.",
      "what_to_do": "Prototype a critic step before upgrading your agent's model.",
      "sources": [
        { "url": "https://example.org/papers/verify-then-expand", "title": "Verify-then-expand (preprint)", "tier": "T1", "kind": "primary", "fetched_at": "2026-10-11T09:30:00Z" },
        { "url": "https://example.org/papers/verify-then-expand/code", "title": "Verify-then-expand code release", "tier": "T1", "kind": "primary" }
      ],
      "facts": [
        { "label": "Success rate, small model with critic", "value": 62.5, "unit": "%", "source_ref": 0, "quote": "62.5% of tasks solved (Table 2)" },
        { "label": "Success rate, 4x larger model", "value": 55.1, "unit": "%", "source_ref": 0, "quote": "55.1% for the 4x larger baseline (Table 2)" }
      ],
      "visuals": [
        {
          "kind": "mermaid",
          "id": "verify-then-expand-method",
          "title": "The verify-then-expand loop",
          "alt": "Flowchart: sample plans, score them with a critic, expand plans above the threshold, prune the rest, and repeat",
          "source_note": "Figure 1 of the paper",
          "block": "method",
          "code": "flowchart LR\n  A[Sample candidate plans] --> B[Score with critic]\n  B --> C{Above threshold?}\n  C -- yes --> D[Expand branch]\n  C -- no --> E[Prune]\n  D --> B"
        },
        {
          "kind": "vega-lite",
          "id": "verify-then-expand-results",
          "title": "Tasks solved by method",
          "alt": "Bar chart: critic-guided small model 62.5%, 4x larger model 55.1%, small model without critic 41.0%",
          "source_note": "Table 2 of the paper",
          "block": "results",
          "spec": {
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "data": { "values": [ { "method": "Small + critic", "solved": 62.5 }, { "method": "4x larger model", "solved": 55.1 }, { "method": "Small, no critic", "solved": 41.0 } ] },
            "mark": { "type": "bar" },
            "encoding": {
              "y": { "field": "method", "type": "nominal", "sort": "-x", "title": null },
              "x": { "field": "solved", "type": "quantitative", "title": "Tasks solved (%)", "scale": { "domain": [0, 100] } }
            }
          }
        },
        {
          "kind": "image-ref",
          "id": "verify-then-expand-figure",
          "title": "Figure 1",
          "alt": "PulseAI logo used as a stand-in for the paper's Figure 1",
          "source_note": "Sample stand-in image",
          "block": "figures",
          "image": {
            "url": "https://raw.githubusercontent.com/Mordris/PulseAI/main/docs/assets/logo-light.svg",
            "caption": "Sample image: the PulseAI logo stands in for the paper's Figure 1",
            "credit": "PulseAI",
            "alt": "PulseAI logo",
            "license": "MIT"
          }
        }
      ],
      "images": [],
      "detail": {
        "peer_reviewed": false,
        "authors": ["A. Example", "B. Sample", "C. Placeholder"],
        "affiliations": ["Example University", "Sample Research Lab"],
        "tldr": "Critic-guided search lets a small model beat a 4x larger one on long-horizon agent tasks.",
        "plain_explanation": "Before acting, the agent drafts several plans, asks a second model to grade them, and only continues with the best ones.",
        "problem": "Long agent tasks fail because early mistakes compound.",
        "key_idea": "Score candidate plans with a critic and expand only the branches above a threshold.",
        "method_steps": ["Sample several candidate plans", "Score each plan with a critic model", "Expand plans above the threshold", "Prune the rest and repeat"],
        "critical_review": ["Preprint, not yet peer reviewed", "The critic and the agent share a model family, which may inflate agreement", "Compute cost per task is about 2.3x the baseline"],
        "reproducibility": { "code_url": "https://example.org/papers/verify-then-expand/code", "license": "MIT" },
        "takeaway": "Try a critic loop before upgrading models; budget for roughly twice the inference cost.",
        "reading_guide": {
          "sections": ["Section 3 (method)", "Table 2 (results)", "Section 6 (limitations)"],
          "glossary": { "Critic": "A model that scores plans instead of producing them", "Long-horizon task": "A task that needs more than twenty tool calls" },
          "reading_minutes": 35,
          "difficulty": "intermediate"
        }
      }
    },
    {
      "id": "sparse-memory-routing",
      "section": "research",
      "type": "paper",
      "title": "Sparse memory routing cuts agent context costs by 38%",
      "entity_key": "paper/sparse-memory-routing",
      "impact": 4,
      "novelty": 4,
      "relevance": 4,
      "confidence": "confirmed",
      "summary": "Routing each step to only the relevant memory shards reduced tokens per task by 38% with no loss in success rate.",
      "why_it_matters": "Context cost is the main driver of agent run cost.",
      "sources": [
        { "url": "https://example.org/papers/sparse-memory-routing", "title": "Sparse memory routing (accepted paper)", "tier": "T1", "kind": "primary" }
      ],
      "facts": [
        { "label": "Token reduction", "value": 38, "unit": "%", "source_ref": 0, "quote": "38% fewer tokens per task" }
      ],
      "visuals": [],
      "images": [],
      "detail": {
        "venue": "Example Conference 2026",
        "peer_reviewed": true,
        "authors": ["D. Example", "E. Sample"],
        "tldr": "Load only relevant memory shards at each step to cut context cost by 38%.",
        "plain_explanation": "Instead of putting all memory in every prompt, a small router picks the few pieces each step needs.",
        "problem": "Agents re-send large memories on every step.",
        "key_idea": "A learned router selects memory shards per step.",
        "method_steps": ["Split memory into shards", "Train a router on task traces", "Load only routed shards per step"],
        "critical_review": ["Router training needs task traces you may not have"],
        "reproducibility": {},
        "takeaway": "Shard agent memory and route per step if context cost dominates.",
        "reading_guide": {
          "sections": ["Section 4"],
          "glossary": { "Shard": "A self-contained slice of memory" },
          "reading_minutes": 20,
          "difficulty": "advanced"
        }
      }
    },
    {
      "id": "tool-use-eval-survey",
      "section": "research",
      "type": "paper",
      "title": "A survey of tool-use evaluation for language agents",
      "entity_key": "paper/tool-use-eval-survey",
      "impact": 2,
      "novelty": 2,
      "relevance": 3,
      "confidence": "confirmed",
      "summary": "A survey that groups 48 tool-use benchmarks by what they measure.",
      "why_it_matters": "A map for picking the right benchmark.",
      "sources": [
        { "url": "https://example.org/papers/tool-use-eval-survey", "title": "Tool-use evaluation survey (preprint)", "tier": "T1", "kind": "primary" }
      ],
      "facts": [],
      "visuals": [],
      "images": [],
      "detail": {
        "peer_reviewed": false,
        "authors": ["F. Example"],
        "tldr": "48 tool-use benchmarks, grouped by what they actually measure.",
        "plain_explanation": "The authors sort benchmarks into accuracy, robustness, and cost families.",
        "problem": "Benchmarks with similar names measure different things.",
        "key_idea": "A taxonomy of tool-use benchmarks.",
        "method_steps": ["Collect benchmarks", "Classify them by measured property"],
        "critical_review": ["No new experiments"],
        "reproducibility": {},
        "takeaway": "Use the taxonomy table to pick benchmarks.",
        "reading_guide": {
          "sections": ["Table 1"],
          "glossary": {},
          "reading_minutes": 10,
          "difficulty": "intro"
        }
      }
    },
    {
      "id": "agents-in-production-year-one",
      "section": "research",
      "type": "article",
      "title": "What a year of running agents in production taught one platform team",
      "entity_key": "article/example-engineering/agents-year-one",
      "impact": 3,
      "novelty": 3,
      "relevance": 5,
      "confidence": "confirmed",
      "summary": "A platform team describes budgets, evaluation gates, and rollback practices from a year of production agents.",
      "why_it_matters": "Concrete operational lessons that rarely appear in papers.",
      "sources": [
        { "url": "https://example.com/engineering/agents-year-one", "title": "Example Engineering blog", "tier": "T1", "kind": "primary" }
      ],
      "facts": [],
      "visuals": [],
      "images": [],
      "detail": {
        "author": "G. Example",
        "publication": "Example Engineering",
        "key_points": [
          "Hard token budgets per task prevented runaway costs.",
          "Every prompt change ships behind an evaluation gate.",
          "Rollbacks are rehearsed monthly."
        ],
        "reading_minutes": 14,
        "worth_full_read": true,
        "worth_reason": "The evaluation-gate section has reusable checklists."
      }
    },
    {
      "id": "pyfetchkit-path-traversal",
      "section": "oss",
      "type": "security_advisory",
      "title": "Critical path traversal in pyfetchkit's download helper",
      "entity_key": "advisory/pyfetchkit/psa-2026-0142",
      "impact": 5,
      "novelty": 4,
      "relevance": 4,
      "confidence": "confirmed",
      "summary": "pyfetchkit before 4.2.1 writes downloaded files outside the target directory when an archive contains ../ paths.",
      "why_it_matters": "Agent tools that download and unpack archives with pyfetchkit can overwrite arbitrary files.",
      "what_to_do": "Upgrade to pyfetchkit 4.2.1 and re-scan containers that bundle older versions.",
      "sources": [
        { "url": "https://example.org/advisories/PSA-2026-0142", "title": "PSA-2026-0142", "tier": "T1-data", "kind": "primary" }
      ],
      "facts": [
        { "label": "CVSS", "value": 9.1, "source_ref": 0, "quote": "CVSS 9.1 (Critical)" }
      ],
      "visuals": [],
      "images": [],
      "detail": {
        "advisory_id": "PSA-2026-0142",
        "cvss": 9.1,
        "severity": "critical",
        "affected": "pyfetchkit < 4.2.1",
        "fixed_in": "4.2.1",
        "exploited_in_wild": false,
        "fix_command": "pip install --upgrade \"pyfetchkit>=4.2.1\""
      }
    },
    {
      "id": "rillet-5-0",
      "section": "oss",
      "type": "framework_release",
      "title": "Rillet 5.0 drops Node 20 and ships a new router",
      "entity_key": "rillet/rillet",
      "impact": 3,
      "novelty": 3,
      "relevance": 3,
      "confidence": "confirmed",
      "summary": "The Rillet web framework's 5.0 release requires Node 22 and replaces the file router with a typed router.",
      "why_it_matters": "Apps on Node 20 must upgrade the runtime before upgrading Rillet.",
      "sources": [
        { "url": "https://example.org/rillet/blog/5-0", "title": "Rillet 5.0", "tier": "T1", "kind": "primary" }
      ],
      "facts": [],
      "visuals": [],
      "images": [],
      "detail": {
        "product": "Rillet",
        "version": "5.0.0",
        "previous_version": "4.7.1",
        "changelog": [
          { "tag": "breaking", "text": "Node 20 is no longer supported." },
          { "tag": "new", "text": "Typed router replaces the file router." }
        ],
        "verdict": "assess",
        "migration_notes": "Run rillet migrate router after upgrading Node."
      }
    }
  ],
  "adoption_radar": [
    { "item_id": "lumen-sdk-2-4", "ring": "adopt", "rationale": "Typed tools are stable and remove a common bug class." },
    { "item_id": "relay-cli-3-0", "ring": "trial", "rationale": "Stable now; trial parallel subagents on one repository first." },
    { "item_id": "mcp-inspector-plus", "ring": "assess", "rationale": "Promising, but only three weeks old." },
    { "item_id": "rillet-5-0", "ring": "hold", "rationale": "Wait for the router migration tool to leave beta." }
  ],
  "action_list": [
    { "text": "Upgrade pyfetchkit to 4.2.1 everywhere.", "item_id": "pyfetchkit-path-traversal" },
    { "text": "Benchmark Atlas-3 on your longest agent task.", "item_id": "northwind-atlas-3" },
    { "text": "Prototype a critic step in one agent loop.", "item_id": "verify-then-expand" }
  ],
  "signals": [
    {
      "id": "atlas-3-mini-rumor",
      "section": "models",
      "type": "model_release",
      "title": "Northwind is reportedly preparing a smaller Atlas-3 Mini",
      "entity_key": "northwind/atlas-3-mini",
      "thread_id": "northwind-atlas",
      "impact": 3,
      "novelty": 3,
      "relevance": 4,
      "confidence": "reported",
      "summary": "Two newsletters report a cheaper Atlas-3 Mini for later this quarter; Northwind has not commented.",
      "why_it_matters": "A cheaper Atlas-3 tier would change model routing decisions.",
      "sources": [
        { "url": "https://example.net/newsletter/atlas-3-mini", "title": "Example Newsletter", "tier": "T2", "kind": "secondary" }
      ],
      "facts": [],
      "visuals": [],
      "images": [],
      "detail": { "org": "Northwind Labs", "model": "Atlas-3 Mini", "weights": "closed" }
    }
  ],
  "corrections": [
    {
      "report_date": "2026-10-10",
      "item_id": "example-gpu-pricing",
      "text": "The index fell 6% month over month, not 8% as an earlier draft said."
    }
  ],
  "section_notes": {
    "research": [
      {
        "title": "Venue watch: Example Conference camera-ready deadline",
        "text": "Camera-ready versions are due on 20 October, so expect revised preprints next week.",
        "url": "https://example.org/conference/dates"
      }
    ]
  },
  "methodology": {
    "notes": [
      "Sample edition written by hand for the demo site; every entity is fictional.",
      "The example lab blog was unreachable; its items are missing from this edition."
    ],
    "rejected": [
      { "title": "Atlas-3 benchmark screenshot thread", "reason": "Screenshot only, no primary source", "url": "https://example.net/thread/2" },
      { "title": "Duplicate coverage of Relay CLI 3.0 RC", "reason": "Already covered on 2026-10-10" }
    ]
  }
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest packages/cli/tests/test_examples.py -q`
Expected: PASS. If a report fails validation, the test prints every issue as `<level> <where>: <message>`. Fix the JSON, not the test.

Run: `for f in examples/reports/*/*/*/report.json; do uv run pulse validate "$f" --instance examples; done`
Expected: `…: valid` three times.

- [ ] **Step 7: Commit**

```bash
pnpm biome check --write examples
git add examples/reports packages/cli/tests/test_examples.py
git commit -m "feat(examples): add three sample editions to the demo instance

Fictional entities on IANA example domains, marked meta.sample. The
2026-10-11 showcase uses every item type, visual kind, research group,
signals, a correction, a section note, and a failing source.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 5: Design tokens and `@pulseai/tokens`

**Files:**
- Create: `schema/tokens-resolved.schema.json`
- Create: `tokens/base/font.json`, `tokens/base/size.json`, `tokens/base/palette.json`, `tokens/base/semantic.json`, `tokens/base/modes/light.json`, `tokens/base/modes/dark.json`
- Create: `tokens/themes/pulse/{light,dark}.json`, `tokens/themes/paper/{base,light,dark}.json`, `tokens/themes/terminal/{base,light,dark}.json`
- Create: `packages/tokens/package.json`, `packages/tokens/tsconfig.json`
- Create: `packages/tokens/src/{layers,overrides,resolve,css,build,index}.ts`
- Create: `packages/tokens/test/build.test.ts`
- Regenerate: `packages/cli/src/pulseai/models/tokens_resolved.py`, `packages/contracts/src/generated/`

**Interfaces:**
- Consumes: `compile`, `getSchema`, `validator`, `JsonSchema`, `TokensResolvedSchema` from `@pulseai/contracts` (Task 2).
- Produces (`@pulseai/tokens`):
  - Building: `buildTokens({ engineDir?, instanceDir?, preset, overrides?, sections }): Promise<TokenBuild>`, where `TokenBuild = { resolved: Record<Mode, ResolvedTokens>; css: string; fonts: string[] }`; `writeTokenBuild(build, outDir)` writes `tokens.css`, `light.json` and `dark.json`; `readResolved(dir, mode): ResolvedTokens`.
  - Lookup: `token(resolved, path): ResolvedToken` (throws `TokenError` naming the theme), `MODES` (from the schema enum: `["light", "dark"]`), `CSS_PREFIX = "pulse"` (a token `a.b.c` becomes `--pulse-a-b-c`).
  - Layers: `presetNames(roots, modes)`, `ENGINE_TOKENS_DIR` (found through the package name, like `DEFAULT_SCHEMA_DIR` in Task 2), `TokenError`, `type SectionColor = { id; color_token }`, `type ThemeOverrides = ConfigSchema.ThemeOverrides`.
- Token layering, lowest precedence first, each root contributing `base/**` (except `base/modes/`), `base/modes/<mode>.json`, `themes/<preset>/base.json` and `themes/<preset>/<mode>.json`:
  1. the engine root `tokens/`
  2. the instance root `<instance>/tokens/`
  3. `config.theme.overrides`, applied last: `accent`, `font_display` and `font_body` replace the tokens whose `$extensions["org.pulseai"].override` names that key; `sections.<id>` replaces that section's `color_token`.
- Semantic tones: `color.confidence.*`, `color.severity.*`, `color.ring.*` and `color.changelog.*` alias the status palette, so the frame never maps enum values to colors in code.
- Token extensions (`$extensions["org.pulseai"]`, validated by `tokens-resolved.schema.json#/$defs/extensions`): `contrast_against`, `distinct {set, order?}`, `override`, `fontsource`.
- Palette provenance: section and chart colors are the dataviz reference palette (validated light/dark, adjacent-pair CVD ≥ 8). Every preset's text, secondary, muted and accent colors reach ≥ 4.9:1 on page, raised and sunken surfaces (ColorAide, WCAG 2.1). Task 6 turns this into a gate.

- [ ] **Step 1: Write the resolved-token schema**

`schema/tokens-resolved.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:pulseai:schema:tokens-resolved",
  "title": "ResolvedTokens",
  "description": "Design tokens for one theme mode after layering (engine, preset, instance, config overrides) and alias resolution. Written by @pulseai/tokens; read by the site and by `pulse tokens check`.",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "preset", "mode", "tokens"],
  "properties": {
    "schema_version": { "const": 1 },
    "preset": { "$ref": "#/$defs/id" },
    "mode": { "enum": ["light", "dark"] },
    "tokens": {
      "type": "object",
      "propertyNames": { "$ref": "#/$defs/path" },
      "additionalProperties": { "$ref": "#/$defs/token" }
    }
  },
  "$defs": {
    "id": { "type": "string", "pattern": "^[a-z0-9]+(?:[_-][a-z0-9]+)*$" },
    "path": { "type": "string", "pattern": "^[a-z0-9_]+(?:\\.[a-z0-9_]+)*$" },
    "token": {
      "title": "ResolvedToken",
      "type": "object",
      "additionalProperties": false,
      "required": ["value", "type", "name"],
      "properties": {
        "value": { "type": ["string", "number"] },
        "type": { "type": "string", "minLength": 1 },
        "name": { "type": "string", "pattern": "^--[a-z0-9-]+$" },
        "extensions": { "$ref": "#/$defs/extensions" }
      }
    },
    "extensions": {
      "title": "TokenExtensions",
      "description": "The org.pulseai entry of a token's $extensions.",
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "contrast_against": {
          "description": "Surface tokens this (text) color must reach quality.text_contrast_min against.",
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/path" }
        },
        "distinct": {
          "title": "DistinctMember",
          "description": "Membership in a set of colors that must stay distinguishable. With order on every member, only neighbours are compared (categorical chart order); otherwise every pair is.",
          "type": "object",
          "additionalProperties": false,
          "required": ["set"],
          "properties": {
            "set": { "$ref": "#/$defs/id" },
            "order": { "type": "integer", "minimum": 1 }
          }
        },
        "override": {
          "description": "Key of config.theme.overrides that replaces this token's value.",
          "$ref": "#/$defs/id"
        },
        "fontsource": {
          "description": "Fontsource package that provides this font family.",
          "type": "string",
          "pattern": "^@?[a-z0-9][a-z0-9._-]*(?:/[a-z0-9][a-z0-9._-]*)?$"
        }
      }
    }
  }
}
```

Run: `uv run python scripts/generate_models.py && pnpm --filter @pulseai/contracts generate`
Expected: new `packages/cli/src/pulseai/models/tokens_resolved.py` and `packages/contracts/src/generated/tokens-resolved.ts` (namespace `TokensResolvedSchema`).

- [ ] **Step 2: Write the token files**

`tokens/base/font.json`:

```json
{
  "font": {
    "family": {
      "$type": "fontFamily",
      "body": {
        "$value": ["Inter Variable", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        "$extensions": {
          "org.pulseai": { "override": "font_body", "fontsource": "@fontsource-variable/inter" }
        }
      },
      "display": {
        "$value": ["Newsreader Variable", "Georgia", "Cambria", "serif"],
        "$extensions": {
          "org.pulseai": {
            "override": "font_display",
            "fontsource": "@fontsource-variable/newsreader"
          }
        }
      },
      "mono": {
        "$value": [
          "JetBrains Mono Variable",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace"
        ],
        "$extensions": { "org.pulseai": { "fontsource": "@fontsource-variable/jetbrains-mono" } }
      }
    },
    "size": {
      "$type": "dimension",
      "xs": { "$value": { "value": 0.75, "unit": "rem" } },
      "sm": { "$value": { "value": 0.875, "unit": "rem" } },
      "md": { "$value": { "value": 1, "unit": "rem" } },
      "lg": { "$value": { "value": 1.125, "unit": "rem" } },
      "xl": { "$value": { "value": 1.375, "unit": "rem" } },
      "2xl": { "$value": { "value": 1.75, "unit": "rem" } },
      "3xl": { "$value": { "value": 2.5, "unit": "rem" } }
    },
    "weight": {
      "$type": "fontWeight",
      "regular": { "$value": 400 },
      "medium": { "$value": 500 },
      "semibold": { "$value": 600 },
      "bold": { "$value": 700 }
    },
    "line_height": {
      "$type": "number",
      "tight": { "$value": 1.2 },
      "normal": { "$value": 1.5 },
      "relaxed": { "$value": 1.7 }
    }
  }
}
```

`tokens/base/size.json`:

```json
{
  "space": {
    "$type": "dimension",
    "1": { "$value": { "value": 0.25, "unit": "rem" } },
    "2": { "$value": { "value": 0.5, "unit": "rem" } },
    "3": { "$value": { "value": 0.75, "unit": "rem" } },
    "4": { "$value": { "value": 1, "unit": "rem" } },
    "5": { "$value": { "value": 1.5, "unit": "rem" } },
    "6": { "$value": { "value": 2, "unit": "rem" } },
    "7": { "$value": { "value": 3, "unit": "rem" } },
    "8": { "$value": { "value": 4, "unit": "rem" } }
  },
  "radius": {
    "$type": "dimension",
    "sm": { "$value": { "value": 4, "unit": "px" } },
    "md": { "$value": { "value": 8, "unit": "px" } },
    "lg": { "$value": { "value": 12, "unit": "px" } },
    "pill": { "$value": { "value": 999, "unit": "px" } }
  },
  "border": {
    "width": {
      "$type": "dimension",
      "thin": { "$value": { "value": 1, "unit": "px" } },
      "thick": { "$value": { "value": 2, "unit": "px" } }
    }
  },
  "layout": {
    "$type": "dimension",
    "content_width": { "$value": { "value": 72, "unit": "rem" } },
    "reading_width": { "$value": { "value": 44, "unit": "rem" } }
  },
  "chart": {
    "$type": "number",
    "height": { "$value": 240 },
    "line_width": { "$value": 2 },
    "point_size": { "$value": 64 },
    "bar_corner_radius": { "$value": 4 },
    "label_size": { "$value": 11 },
    "title_size": { "$value": 13 },
    "heatmap_cell": { "$value": 18 }
  }
}
```

`tokens/base/palette.json` (the dataviz reference palette; hex values only live in token files):

```json
{
  "palette": {
    "$type": "color",
    "blue": {
      "100": { "$value": "#cde2fb" },
      "150": { "$value": "#b7d3f6" },
      "200": { "$value": "#9ec5f4" },
      "250": { "$value": "#86b6ef" },
      "300": { "$value": "#6da7ec" },
      "350": { "$value": "#5598e7" },
      "400": { "$value": "#3987e5" },
      "450": { "$value": "#2a78d6" },
      "500": { "$value": "#256abf" },
      "550": { "$value": "#1c5cab" },
      "600": { "$value": "#184f95" },
      "650": { "$value": "#104281" },
      "700": { "$value": "#0d366b" }
    },
    "amber": { "400": { "$value": "#e6b000" } },
    "category": {
      "light": {
        "1": { "$value": "#2a78d6" },
        "2": { "$value": "#eb6834" },
        "3": { "$value": "#1baf7a" },
        "4": { "$value": "#eda100" },
        "5": { "$value": "#e87ba4" },
        "6": { "$value": "#008300" },
        "7": { "$value": "#4a3aa7" },
        "8": { "$value": "#e34948" }
      },
      "dark": {
        "1": { "$value": "#3987e5" },
        "2": { "$value": "#d95926" },
        "3": { "$value": "#199e70" },
        "4": { "$value": "#c98500" },
        "5": { "$value": "#d55181" },
        "6": { "$value": "#008300" },
        "7": { "$value": "#9085e9" },
        "8": { "$value": "#e66767" }
      }
    },
    "status": {
      "good": { "$value": "#0ca30c" },
      "warning": { "$value": "#fab219" },
      "serious": { "$value": "#ec835a" },
      "critical": { "$value": "#d03b3b" }
    }
  }
}
```

`tokens/base/semantic.json` (the color each enum value wears: the frame looks up `color.<enum>.<value>` and fails the build when a value has no token):

```json
{
  "color": {
    "$type": "color",
    "confidence": {
      "confirmed": { "$value": "{color.status.good}" },
      "reported": { "$value": "{color.status.warning}" },
      "rumor": { "$value": "{color.status.critical}" }
    },
    "severity": {
      "low": { "$value": "{color.status.good}" },
      "medium": { "$value": "{color.status.warning}" },
      "high": { "$value": "{color.status.serious}" },
      "critical": { "$value": "{color.status.critical}" }
    },
    "ring": {
      "adopt": { "$value": "{color.status.good}" },
      "trial": { "$value": "{color.accent.default}" },
      "assess": { "$value": "{color.status.warning}" },
      "hold": { "$value": "{color.status.critical}" }
    },
    "changelog": {
      "new": { "$value": "{color.status.good}" },
      "fix": { "$value": "{color.accent.default}" },
      "perf": { "$value": "{color.status.good}" },
      "breaking": { "$value": "{color.status.critical}" },
      "deprecation": { "$value": "{color.status.warning}" },
      "security": { "$value": "{color.status.serious}" }
    }
  }
}
```

`tokens/base/modes/light.json` (colors every preset shares in light mode):

```json
{
  "color": {
    "section": {
      "$type": "color",
      "models": { "$value": "{palette.category.light.1}" },
      "tooling": { "$value": "{palette.category.light.2}" },
      "research": { "$value": "{palette.category.light.3}" },
      "oss": { "$value": "{palette.category.light.4}" }
    },
    "chart": {
      "$type": "color",
      "category": {
        "1": {
          "$value": "{palette.category.light.1}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 1 } } }
        },
        "2": {
          "$value": "{palette.category.light.2}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 2 } } }
        },
        "3": {
          "$value": "{palette.category.light.3}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 3 } } }
        },
        "4": {
          "$value": "{palette.category.light.4}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 4 } } }
        },
        "5": {
          "$value": "{palette.category.light.5}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 5 } } }
        },
        "6": {
          "$value": "{palette.category.light.6}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 6 } } }
        },
        "7": {
          "$value": "{palette.category.light.7}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 7 } } }
        },
        "8": {
          "$value": "{palette.category.light.8}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 8 } } }
        }
      },
      "ramp": {
        "low": { "$value": "{palette.blue.100}" },
        "high": { "$value": "{palette.blue.700}" }
      }
    },
    "status": {
      "$type": "color",
      "good": { "$value": "{palette.status.good}" },
      "warning": { "$value": "{palette.status.warning}" },
      "serious": { "$value": "{palette.status.serious}" },
      "critical": { "$value": "{palette.status.critical}" }
    }
  }
}
```

`tokens/base/modes/dark.json`:

```json
{
  "color": {
    "section": {
      "$type": "color",
      "models": { "$value": "{palette.category.dark.1}" },
      "tooling": { "$value": "{palette.category.dark.2}" },
      "research": { "$value": "{palette.category.dark.3}" },
      "oss": { "$value": "{palette.amber.400}" }
    },
    "chart": {
      "$type": "color",
      "category": {
        "1": {
          "$value": "{palette.category.dark.1}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 1 } } }
        },
        "2": {
          "$value": "{palette.category.dark.2}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 2 } } }
        },
        "3": {
          "$value": "{palette.category.dark.3}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 3 } } }
        },
        "4": {
          "$value": "{palette.category.dark.4}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 4 } } }
        },
        "5": {
          "$value": "{palette.category.dark.5}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 5 } } }
        },
        "6": {
          "$value": "{palette.category.dark.6}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 6 } } }
        },
        "7": {
          "$value": "{palette.category.dark.7}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 7 } } }
        },
        "8": {
          "$value": "{palette.category.dark.8}",
          "$extensions": { "org.pulseai": { "distinct": { "set": "chart-category", "order": 8 } } }
        }
      },
      "ramp": {
        "low": { "$value": "{palette.blue.650}" },
        "high": { "$value": "{palette.blue.100}" }
      }
    },
    "status": {
      "$type": "color",
      "good": { "$value": "{palette.status.good}" },
      "warning": { "$value": "{palette.status.warning}" },
      "serious": { "$value": "{palette.status.serious}" },
      "critical": { "$value": "{palette.status.critical}" }
    }
  }
}
```

`tokens/themes/pulse/light.json`:

```json
{
  "color": {
    "surface": {
      "$type": "color",
      "page": { "$value": "#f9f9f7" },
      "raised": { "$value": "#fcfcfb" },
      "sunken": { "$value": "#f0efec" }
    },
    "text": {
      "$type": "color",
      "primary": {
        "$value": "#0b0b0b",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      },
      "secondary": {
        "$value": "#52514e",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      },
      "muted": {
        "$value": "#686760",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      }
    },
    "border": {
      "$type": "color",
      "subtle": { "$value": "#e1e0d9" },
      "strong": { "$value": "#c3c2b7" }
    },
    "accent": {
      "$type": "color",
      "default": {
        "$value": "#1c5cab",
        "$extensions": {
          "org.pulseai": {
            "override": "accent",
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      }
    },
    "focus": { "$type": "color", "ring": { "$value": "{palette.blue.450}" } },
    "chart": {
      "$type": "color",
      "grid": { "$value": "#e1e0d9" },
      "axis": { "$value": "#c3c2b7" },
      "label": { "$value": "{color.text.secondary}" },
      "surface": { "$value": "{color.surface.raised}" }
    }
  }
}
```

`tokens/themes/pulse/dark.json`:

```json
{
  "color": {
    "surface": {
      "$type": "color",
      "page": { "$value": "#0d0d0d" },
      "raised": { "$value": "#1a1a19" },
      "sunken": { "$value": "#141413" }
    },
    "text": {
      "$type": "color",
      "primary": {
        "$value": "#ffffff",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      },
      "secondary": {
        "$value": "#c3c2b7",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      },
      "muted": {
        "$value": "#a3a29b",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      }
    },
    "border": {
      "$type": "color",
      "subtle": { "$value": "#2c2c2a" },
      "strong": { "$value": "#383835" }
    },
    "accent": {
      "$type": "color",
      "default": {
        "$value": "#6da7ec",
        "$extensions": {
          "org.pulseai": {
            "override": "accent",
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      }
    },
    "focus": { "$type": "color", "ring": { "$value": "{palette.blue.300}" } },
    "chart": {
      "$type": "color",
      "grid": { "$value": "#2c2c2a" },
      "axis": { "$value": "#383835" },
      "label": { "$value": "{color.text.secondary}" },
      "surface": { "$value": "{color.surface.raised}" }
    }
  }
}
```

`tokens/themes/paper/base.json`:

```json
{
  "font": {
    "family": {
      "$type": "fontFamily",
      "body": {
        "$value": ["Source Serif 4 Variable", "Georgia", "Cambria", "serif"],
        "$extensions": { "org.pulseai": { "fontsource": "@fontsource-variable/source-serif-4" } }
      }
    }
  }
}
```

`tokens/themes/paper/light.json`:

```json
{
  "color": {
    "surface": {
      "$type": "color",
      "page": { "$value": "#faf6ef" },
      "raised": { "$value": "#fffdf8" },
      "sunken": { "$value": "#f2ece1" }
    },
    "text": {
      "$type": "color",
      "primary": {
        "$value": "#1f1a14",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      },
      "secondary": {
        "$value": "#5a5045",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      },
      "muted": {
        "$value": "#6b6155",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      }
    },
    "border": {
      "$type": "color",
      "subtle": { "$value": "#e6dccb" },
      "strong": { "$value": "#cbbda6" }
    },
    "accent": {
      "$type": "color",
      "default": {
        "$value": "#8a3b12",
        "$extensions": {
          "org.pulseai": {
            "override": "accent",
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      }
    },
    "focus": { "$type": "color", "ring": { "$value": "{palette.blue.450}" } },
    "chart": {
      "$type": "color",
      "grid": { "$value": "#e6dccb" },
      "axis": { "$value": "#cbbda6" },
      "label": { "$value": "{color.text.secondary}" },
      "surface": { "$value": "{color.surface.raised}" }
    }
  }
}
```

`tokens/themes/paper/dark.json`:

```json
{
  "color": {
    "surface": {
      "$type": "color",
      "page": { "$value": "#17140f" },
      "raised": { "$value": "#201c16" },
      "sunken": { "$value": "#120f0b" }
    },
    "text": {
      "$type": "color",
      "primary": {
        "$value": "#f5efe6",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      },
      "secondary": {
        "$value": "#cfc5b6",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      },
      "muted": {
        "$value": "#a99e8e",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      }
    },
    "border": {
      "$type": "color",
      "subtle": { "$value": "#332c22" },
      "strong": { "$value": "#4a4033" }
    },
    "accent": {
      "$type": "color",
      "default": {
        "$value": "#e7a378",
        "$extensions": {
          "org.pulseai": {
            "override": "accent",
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      }
    },
    "focus": { "$type": "color", "ring": { "$value": "{palette.blue.300}" } },
    "chart": {
      "$type": "color",
      "grid": { "$value": "#332c22" },
      "axis": { "$value": "#4a4033" },
      "label": { "$value": "{color.text.secondary}" },
      "surface": { "$value": "{color.surface.raised}" }
    }
  }
}
```

`tokens/themes/terminal/base.json`:

```json
{
  "font": {
    "family": {
      "$type": "fontFamily",
      "body": {
        "$value": [
          "JetBrains Mono Variable",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace"
        ],
        "$extensions": { "org.pulseai": { "fontsource": "@fontsource-variable/jetbrains-mono" } }
      },
      "display": {
        "$value": [
          "JetBrains Mono Variable",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace"
        ],
        "$extensions": { "org.pulseai": { "fontsource": "@fontsource-variable/jetbrains-mono" } }
      }
    }
  },
  "radius": {
    "$type": "dimension",
    "sm": { "$value": { "value": 0, "unit": "px" } },
    "md": { "$value": { "value": 0, "unit": "px" } },
    "lg": { "$value": { "value": 0, "unit": "px" } }
  }
}
```

`tokens/themes/terminal/light.json`:

```json
{
  "color": {
    "surface": {
      "$type": "color",
      "page": { "$value": "#f4f7f4" },
      "raised": { "$value": "#ffffff" },
      "sunken": { "$value": "#e9eee9" }
    },
    "text": {
      "$type": "color",
      "primary": {
        "$value": "#0f1a12",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      },
      "secondary": {
        "$value": "#3b4a3f",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      },
      "muted": {
        "$value": "#55645a",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      }
    },
    "border": {
      "$type": "color",
      "subtle": { "$value": "#d5ded6" },
      "strong": { "$value": "#b3c1b5" }
    },
    "accent": {
      "$type": "color",
      "default": {
        "$value": "#0b6e38",
        "$extensions": {
          "org.pulseai": {
            "override": "accent",
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      }
    },
    "focus": { "$type": "color", "ring": { "$value": "{palette.blue.450}" } },
    "chart": {
      "$type": "color",
      "grid": { "$value": "#d5ded6" },
      "axis": { "$value": "#b3c1b5" },
      "label": { "$value": "{color.text.secondary}" },
      "surface": { "$value": "{color.surface.raised}" }
    }
  }
}
```

`tokens/themes/terminal/dark.json`:

```json
{
  "color": {
    "surface": {
      "$type": "color",
      "page": { "$value": "#0a0f0b" },
      "raised": { "$value": "#111a13" },
      "sunken": { "$value": "#070a08" }
    },
    "text": {
      "$type": "color",
      "primary": {
        "$value": "#d7f5df",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      },
      "secondary": {
        "$value": "#9fc7aa",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      },
      "muted": {
        "$value": "#84ab8f",
        "$extensions": {
          "org.pulseai": {
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      }
    },
    "border": {
      "$type": "color",
      "subtle": { "$value": "#1f2b22" },
      "strong": { "$value": "#2f4034" }
    },
    "accent": {
      "$type": "color",
      "default": {
        "$value": "#4ade80",
        "$extensions": {
          "org.pulseai": {
            "override": "accent",
            "contrast_against": [
              "color.surface.page",
              "color.surface.raised",
              "color.surface.sunken"
            ]
          }
        }
      }
    },
    "focus": { "$type": "color", "ring": { "$value": "{palette.blue.300}" } },
    "chart": {
      "$type": "color",
      "grid": { "$value": "#1f2b22" },
      "axis": { "$value": "#2f4034" },
      "label": { "$value": "{color.text.secondary}" },
      "surface": { "$value": "{color.surface.raised}" }
    }
  }
}
```

- [ ] **Step 3: Create the package and write the failing tests**

`packages/tokens/package.json`:

```json
{
  "name": "@pulseai/tokens",
  "version": "0.1.0",
  "private": true,
  "description": "PulseAI design tokens: DTCG layers resolved with Style Dictionary",
  "license": "MIT",
  "type": "module",
  "exports": {
    ".": "./src/index.ts",
    "./package.json": "./package.json"
  },
  "scripts": {
    "typecheck": "tsc -p tsconfig.json",
    "test": "vitest run"
  }
}
```

Run: `pnpm --filter @pulseai/tokens add style-dictionary zod && pnpm --filter @pulseai/tokens add @pulseai/contracts --workspace && pnpm --filter @pulseai/tokens add -D @types/node typescript vitest`

`packages/tokens/tsconfig.json`:

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": { "types": ["node"] },
  "include": ["src", "test", "scripts"]
}
```

`packages/tokens/test/build.test.ts`:

```ts
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { validator } from "@pulseai/contracts";
import { describe, expect, it } from "vitest";
import {
  buildTokens,
  CSS_FILE,
  ENGINE_TOKENS_DIR,
  MODES,
  mergeTokens,
  readResolved,
  TokenError,
  token,
  writeTokenBuild,
} from "../src/index.ts";

const SECTIONS = [
  { id: "models", color_token: "color.section.models" },
  { id: "tooling", color_token: "color.section.tooling" },
  { id: "research", color_token: "color.section.research" },
  { id: "oss", color_token: "color.section.oss" },
];

function instanceWith(files: Record<string, unknown>): string {
  const dir = mkdtempSync(join(tmpdir(), "pulse-tokens-"));
  for (const [rel, content] of Object.entries(files)) {
    const path = join(dir, "tokens", rel);
    mkdirSync(join(path, ".."), { recursive: true });
    writeFileSync(path, JSON.stringify(content));
  }
  return dir;
}

describe("mergeTokens", () => {
  it("merges objects and lets later trees replace values and arrays", () => {
    const merged = mergeTokens(
      { a: { $value: 1, $type: "number" }, f: { $value: ["A", "B"] } },
      { a: { $value: 2 }, f: { $value: ["C"] } },
    );
    expect(merged).toEqual({ a: { $value: 2, $type: "number" }, f: { $value: ["C"] } });
  });
});

describe("buildTokens", () => {
  it("resolves both modes of the default preset", async () => {
    const build = await buildTokens({ preset: "pulse", sections: SECTIONS });
    expect(MODES).toEqual(["light", "dark"]);
    expect(token(build.resolved.light, "color.surface.page").value).toBe("#f9f9f7");
    expect(token(build.resolved.dark, "color.surface.page").value).toBe("#0d0d0d");
    expect(token(build.resolved.light, "color.section.models").value).toBe("#2a78d6");
    expect(token(build.resolved.light, "space.4")).toMatchObject({
      value: "1rem",
      name: "--pulse-space-4",
    });
    expect(
      token(build.resolved.light, "color.text.primary").extensions?.contrast_against,
    ).toContain("color.surface.page");
  });

  it("writes shared values once and dark values for both the toggle and the OS setting", async () => {
    const { css } = await buildTokens({ preset: "pulse", sections: SECTIONS });
    const [root, light, dark, media] = css.split("\n\n").slice(1);
    expect(root).toContain("--pulse-space-4: 1rem;");
    expect(light).toMatch(/^:root,\n:root\[data-theme="light"\] \{/);
    expect(light).toContain("--pulse-color-surface-page: #f9f9f7;");
    expect(dark).toMatch(/^:root\[data-theme="dark"\] \{/);
    expect(dark).toContain("--pulse-color-surface-page: #0d0d0d;");
    expect(dark).not.toContain("--pulse-space-4");
    expect(media).toContain(':root:not([data-theme="light"])');
    expect(media).toContain("--pulse-color-surface-page: #0d0d0d;");
  });

  it("lists the Fontsource packages of the preset's fonts", async () => {
    expect((await buildTokens({ preset: "pulse", sections: SECTIONS })).fonts).toEqual([
      "@fontsource-variable/inter",
      "@fontsource-variable/jetbrains-mono",
      "@fontsource-variable/newsreader",
    ]);
    expect((await buildTokens({ preset: "paper", sections: SECTIONS })).fonts).toEqual([
      "@fontsource-variable/jetbrains-mono",
      "@fontsource-variable/newsreader",
      "@fontsource-variable/source-serif-4",
    ]);
  });

  it("builds every engine preset", async () => {
    for (const preset of ["pulse", "paper", "terminal"]) {
      const build = await buildTokens({ preset, sections: SECTIONS });
      expect(build.resolved.dark.preset).toBe(preset);
    }
  });

  it("names the available presets when the preset is unknown", async () => {
    await expect(buildTokens({ preset: "neon", sections: SECTIONS })).rejects.toThrow(
      'unknown theme preset "neon"; available: paper, pulse, terminal',
    );
  });

  it("lets instance token files override the engine and add presets", async () => {
    // A new preset is a full theme: start from an engine preset and change what differs.
    const brandTheme = (mode: string, page: string) => {
      const theme = JSON.parse(
        readFileSync(join(ENGINE_TOKENS_DIR, "themes/pulse", `${mode}.json`), "utf8"),
      );
      theme.color.surface.page.$value = page;
      return theme;
    };
    const instanceDir = instanceWith({
      "themes/pulse/light.json": { color: { surface: { page: { $value: "#fffef0" } } } },
      "themes/brand/light.json": brandTheme("light", "#ffffff"),
      "themes/brand/dark.json": brandTheme("dark", "#000000"),
    });
    const pulse = await buildTokens({ preset: "pulse", instanceDir, sections: SECTIONS });
    expect(token(pulse.resolved.light, "color.surface.page").value).toBe("#fffef0");
    expect(token(pulse.resolved.dark, "color.surface.page").value).toBe("#0d0d0d");
    const brand = await buildTokens({ preset: "brand", instanceDir, sections: SECTIONS });
    expect(token(brand.resolved.dark, "color.surface.page").value).toBe("#000000");
  });

  it("applies config overrides for accent, fonts, and section colors", async () => {
    const build = await buildTokens({
      preset: "pulse",
      sections: SECTIONS,
      overrides: {
        accent: "#123456",
        font_body: "Atkinson Hyperlegible",
        sections: { models: "#654321" },
      },
    });
    for (const mode of MODES) {
      expect(token(build.resolved[mode], "color.accent.default").value).toBe("#123456");
      expect(token(build.resolved[mode], "color.section.models").value).toBe("#654321");
    }
    expect(token(build.resolved.light, "font.family.body").value).toMatch(
      /^'Atkinson Hyperlegible', system-ui/,
    );
    expect(build.fonts).not.toContain("@fontsource-variable/inter");
  });

  it("rejects an override for a section that does not exist", async () => {
    await expect(
      buildTokens({
        preset: "pulse",
        sections: SECTIONS,
        overrides: { sections: { weather: "#000000" } },
      }),
    ).rejects.toThrow('theme.overrides.sections names unknown section "weather"');
  });

  it("rejects a section whose color token is not defined", async () => {
    await expect(
      buildTokens({
        preset: "pulse",
        sections: [...SECTIONS, { id: "extra", color_token: "color.section.extra" }],
      }),
    ).rejects.toThrow('section "extra" uses color token "color.section.extra"');
  });

  it("reports a broken alias", async () => {
    const instanceDir = instanceWith({
      "themes/pulse/light.json": { color: { surface: { page: { $value: "{palette.nope.1}" } } } },
    });
    await expect(buildTokens({ preset: "pulse", instanceDir, sections: SECTIONS })).rejects.toThrow(
      TokenError,
    );
  });

  it("reports an invalid extension with the token path", async () => {
    const instanceDir = instanceWith({
      "themes/pulse/light.json": {
        color: {
          text: {
            primary: { $extensions: { "org.pulseai": { contrast_against: "color.surface.page" } } },
          },
        },
      },
    });
    await expect(buildTokens({ preset: "pulse", instanceDir, sections: SECTIONS })).rejects.toThrow(
      'color.text.primary: invalid $extensions["org.pulseai"]',
    );
  });

  it("writes CSS and resolved maps that pass the schema", async () => {
    const out = mkdtempSync(join(tmpdir(), "pulse-tokens-out-"));
    const build = await buildTokens({ preset: "pulse", sections: SECTIONS });
    writeTokenBuild(build, out);
    expect(readFileSync(join(out, CSS_FILE), "utf8")).toBe(build.css);
    for (const mode of MODES) {
      const resolved = readResolved(out, mode);
      expect(validator("tokens-resolved").safeParse(resolved).success).toBe(true);
      expect(resolved).toEqual(build.resolved[mode]);
    }
  });
});
```

Run: `pnpm --filter @pulseai/tokens test`
Expected: FAIL with `Cannot find module '../src/index.ts'`.

- [ ] **Step 4: Write the layering**

`packages/tokens/src/layers.ts`:

```ts
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve, sep } from "node:path";

/** A DTCG document or group: nested objects whose leaves carry `$value`. */
export type TokenTree = { [key: string]: unknown };

/** The engine's tokens/ directory, found through the package name (see DEFAULT_SCHEMA_DIR). */
export const ENGINE_TOKENS_DIR = resolve(
  dirname(createRequire(import.meta.url).resolve("@pulseai/tokens/package.json")),
  "../../tokens",
);

const BASE_DIR = "base";
const MODES_DIR = "modes";
const THEMES_DIR = "themes";
const PRESET_BASE = "base.json";

export class TokenError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TokenError";
  }
}

function isTree(value: unknown): value is TokenTree {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Deep-merge DTCG trees; later trees win. Arrays and scalars are replaced, objects are merged. */
export function mergeTokens(...trees: TokenTree[]): TokenTree {
  const merged: TokenTree = {};
  for (const tree of trees) {
    for (const [key, value] of Object.entries(tree)) {
      const current = merged[key];
      merged[key] = isTree(current) && isTree(value) ? mergeTokens(current, value) : value;
    }
  }
  return merged;
}

function readTree(path: string): TokenTree {
  let parsed: unknown;
  try {
    parsed = JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    throw new TokenError(`${path}: cannot read tokens (${(error as Error).message})`);
  }
  if (!isTree(parsed)) {
    throw new TokenError(`${path}: a token file must be a JSON object`);
  }
  return parsed;
}

/** JSON files directly or deeply under base/, except base/modes/, in a stable order. */
function baseFiles(root: string): string[] {
  const dir = join(root, BASE_DIR);
  if (!existsSync(dir)) return [];
  return readdirSync(dir, { recursive: true, encoding: "utf8" })
    .filter((rel) => rel.endsWith(".json") && rel.split(sep)[0] !== MODES_DIR)
    .sort()
    .map((rel) => join(dir, rel));
}

function optional(path: string): string[] {
  return existsSync(path) ? [path] : [];
}

/** Presets that define both modes in any of the roots. */
export function presetNames(roots: string[], modes: readonly string[]): string[] {
  const names = new Set<string>();
  for (const root of roots) {
    const dir = join(root, THEMES_DIR);
    if (!existsSync(dir)) continue;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.isDirectory()) names.add(entry.name);
    }
  }
  return [...names]
    .filter((name) =>
      modes.every((mode) =>
        roots.some((root) => existsSync(join(root, THEMES_DIR, name, `${mode}.json`))),
      ),
    )
    .sort();
}

export interface LayerOptions {
  engineDir: string;
  instanceDir?: string | undefined;
  preset: string;
  mode: string;
  modes: readonly string[];
}

/**
 * Token files for one mode, lowest precedence first: for the engine and then the instance,
 * base/**, base/modes/<mode>.json, themes/<preset>/base.json, themes/<preset>/<mode>.json.
 */
export function layerFiles(options: LayerOptions): string[] {
  const roots = [options.engineDir];
  const instanceTokens = options.instanceDir ? join(options.instanceDir, "tokens") : undefined;
  if (instanceTokens && existsSync(instanceTokens)) roots.push(instanceTokens);
  const presets = presetNames(roots, options.modes);
  if (!presets.includes(options.preset)) {
    throw new TokenError(
      `unknown theme preset "${options.preset}"; available: ${presets.join(", ") || "none"}`,
    );
  }
  return roots.flatMap((root) => [
    ...baseFiles(root),
    ...optional(join(root, BASE_DIR, MODES_DIR, `${options.mode}.json`)),
    ...optional(join(root, THEMES_DIR, options.preset, PRESET_BASE)),
    ...optional(join(root, THEMES_DIR, options.preset, `${options.mode}.json`)),
  ]);
}

export function readLayers(options: LayerOptions): TokenTree {
  return mergeTokens(...layerFiles(options).map(readTree));
}
```

- [ ] **Step 5: Write the overrides**

`packages/tokens/src/overrides.ts`:

```ts
import type { ConfigSchema } from "@pulseai/contracts";
import { TokenError, type TokenTree } from "./layers.ts";

export const EXTENSION = "org.pulseai";

/** config.theme.overrides, typed from schema/config.schema.json. */
export type ThemeOverrides = ConfigSchema.ThemeOverrides;

/** The part of a sections registry entry the token build needs. */
export interface SectionColor {
  id: string;
  color_token: string;
}

export interface TokenLeaf {
  path: string[];
  token: TokenTree;
}

/** Every token (an object with `$value`) in a tree, with its path. */
export function leaves(tree: TokenTree, path: string[] = []): TokenLeaf[] {
  const found: TokenLeaf[] = [];
  for (const [key, value] of Object.entries(tree)) {
    if (
      key.startsWith("$") ||
      value === null ||
      typeof value !== "object" ||
      Array.isArray(value)
    ) {
      continue;
    }
    const child = value as TokenTree;
    if ("$value" in child) {
      found.push({ path: [...path, key], token: child });
    } else {
      found.push(...leaves(child, [...path, key]));
    }
  }
  return found;
}

/** The org.pulseai entry of a token's $extensions, if any. */
export function extensionOf(token: TokenTree): TokenTree | undefined {
  const extensions = token.$extensions;
  if (extensions === null || typeof extensions !== "object") return undefined;
  const entry = (extensions as TokenTree)[EXTENSION];
  return entry !== null && typeof entry === "object" ? (entry as TokenTree) : undefined;
}

/** The token at a dotted path, if the tree defines one. */
export function findToken(tree: TokenTree, path: string): TokenTree | undefined {
  let node: unknown = tree;
  for (const key of path.split(".")) {
    if (node === null || typeof node !== "object") return undefined;
    node = (node as TokenTree)[key];
  }
  return node !== null && typeof node === "object" && "$value" in node
    ? (node as TokenTree)
    : undefined;
}

/**
 * Apply config.theme.overrides to a copy of the tree. A string override replaces every token
 * whose extension names its key; `sections` replaces each listed section's color token.
 */
export function applyOverrides(
  tree: TokenTree,
  overrides: ThemeOverrides,
  sections: readonly SectionColor[],
): TokenTree {
  const result = structuredClone(tree);
  const keyed = overrides as { [key: string]: unknown };
  for (const { token } of leaves(result)) {
    const extension = extensionOf(token);
    const key = extension?.override;
    if (typeof key !== "string") continue;
    const value = keyed[key];
    if (value === undefined) continue;
    if (typeof value !== "string") {
      throw new TokenError(`theme.overrides.${key} must be a string`);
    }
    if (Array.isArray(token.$value)) {
      // A font override keeps the token's fallbacks; the new family is not a Fontsource package.
      token.$value = [value, ...token.$value.slice(1)];
      delete extension?.fontsource;
    } else {
      token.$value = value;
    }
  }
  for (const [sectionId, color] of Object.entries(overrides.sections ?? {})) {
    if (color === undefined) continue;
    const section = sections.find((candidate) => candidate.id === sectionId);
    if (section === undefined) {
      throw new TokenError(`theme.overrides.sections names unknown section "${sectionId}"`);
    }
    const token = findToken(result, section.color_token);
    if (token === undefined) {
      throw new TokenError(missingSectionToken(section));
    }
    token.$value = color;
  }
  return result;
}

export function missingSectionToken(section: SectionColor): string {
  return `section "${section.id}" uses color token "${section.color_token}", which no token file defines`;
}
```

- [ ] **Step 6: Write the resolver**

`packages/tokens/src/resolve.ts`:

```ts
import { compile, getSchema, type JsonSchema, type TokensResolvedSchema } from "@pulseai/contracts";
import StyleDictionary from "style-dictionary";
import type { DesignTokens } from "style-dictionary/types";
import { z } from "zod";
import { TokenError, type TokenTree } from "./layers.ts";
import { EXTENSION, extensionOf, leaves } from "./overrides.ts";

export type ResolvedTokens = TokensResolvedSchema.ResolvedTokens;
export type ResolvedToken = TokensResolvedSchema.ResolvedToken;
export type Mode = ResolvedTokens["mode"];

/** CSS custom properties are named --<prefix>-<token path in kebab case>. */
export const CSS_PREFIX = "pulse";

interface ResolvedSchemaShape {
  properties: { mode: { enum: Mode[] } };
  $defs: { [name: string]: unknown };
}

const resolvedSchema = getSchema("tokens-resolved");
const shape = resolvedSchema as unknown as ResolvedSchemaShape;

/** Theme modes, in the order the schema lists them. */
export const MODES: readonly Mode[] = shape.properties.mode.enum;

const resolvedValidator = compile(resolvedSchema);
const extensionValidator = compile({
  ...(shape.$defs.extensions as object),
  $defs: shape.$defs,
} as JsonSchema);

function checkExtensions(tree: TokenTree): void {
  for (const { path, token } of leaves(tree)) {
    const extension = extensionOf(token);
    if (extension === undefined) continue;
    const result = extensionValidator.safeParse(extension);
    if (!result.success) {
      throw new TokenError(
        `${path.join(".")}: invalid $extensions["${EXTENSION}"]\n${z.prettifyError(result.error)}`,
      );
    }
  }
}

/** Resolve aliases and CSS values for one mode with Style Dictionary. */
export async function resolveMode(
  tree: TokenTree,
  preset: string,
  mode: Mode,
): Promise<ResolvedTokens> {
  checkExtensions(tree);
  const dictionary = new StyleDictionary({
    tokens: tree as DesignTokens,
    usesDtcg: true,
    log: { verbosity: "silent", warnings: "error", errors: { brokenReferences: "throw" } },
    platforms: { css: { transformGroup: "css", prefix: CSS_PREFIX } },
  });
  let all: Awaited<ReturnType<typeof dictionary.getPlatformTokens>>["allTokens"];
  try {
    all = (await dictionary.getPlatformTokens("css")).allTokens;
  } catch (error) {
    throw new TokenError(`${preset} ${mode}: ${(error as Error).message.trim()}`);
  }
  const tokens: { [path: string]: ResolvedToken } = {};
  for (const token of all) {
    const path = token.path.join(".");
    const value: unknown = token.$value;
    if (typeof value !== "string" && typeof value !== "number") {
      throw new TokenError(`${path}: $type "${String(token.$type)}" has no CSS value`);
    }
    const extension = token.$extensions?.[EXTENSION] as ResolvedToken["extensions"] | undefined;
    tokens[path] = {
      value,
      type: String(token.$type),
      name: `--${token.name}`,
      ...(extension === undefined ? {} : { extensions: extension }),
    };
  }
  const resolved: ResolvedTokens = { schema_version: 1, preset, mode, tokens };
  const result = resolvedValidator.safeParse(resolved);
  if (!result.success) {
    throw new TokenError(
      `${preset} ${mode}: resolved tokens are invalid\n${z.prettifyError(result.error)}`,
    );
  }
  return resolved;
}

/** One resolved token; fails with the theme and path when it is missing. */
export function token(resolved: ResolvedTokens, path: string): ResolvedToken {
  const found = resolved.tokens[path];
  if (found === undefined) {
    throw new TokenError(
      `token "${path}" is not defined in the ${resolved.preset} ${resolved.mode} theme`,
    );
  }
  return found;
}
```

- [ ] **Step 7: Write the CSS renderer**

`packages/tokens/src/css.ts`:

```ts
import type { Mode, ResolvedToken, ResolvedTokens } from "./resolve.ts";

const HEADER =
  "/* Generated by @pulseai/tokens from the engine and instance token files. Do not edit. */";

function declarations(tokens: ResolvedToken[], indent: string): string {
  return tokens.map((token) => `${indent}${token.name}: ${token.value};`).join("\n");
}

/**
 * Custom properties for both modes. Values shared by both modes go on :root once. Light values
 * apply by default and under data-theme="light"; dark values apply under data-theme="dark" and,
 * when the reader has not picked a theme, under prefers-color-scheme: dark.
 */
export function renderCss(resolved: Record<Mode, ResolvedTokens>): string {
  const light = resolved.light.tokens;
  const dark = resolved.dark.tokens;
  const shared: ResolvedToken[] = [];
  const lightOnly: ResolvedToken[] = [];
  const darkOnly: ResolvedToken[] = [];
  for (const [path, token] of Object.entries(light)) {
    if (token === undefined) continue;
    const other = dark[path];
    if (other !== undefined && other.value === token.value) {
      shared.push(token);
    } else {
      lightOnly.push(token);
    }
  }
  for (const [path, token] of Object.entries(dark)) {
    if (token !== undefined && light[path]?.value !== token.value) darkOnly.push(token);
  }
  const blocks = [
    HEADER,
    `:root {\n${declarations(shared, "  ")}\n}`,
    `:root,\n:root[data-theme="light"] {\n  color-scheme: light;\n${declarations(lightOnly, "  ")}\n}`,
    `:root[data-theme="dark"] {\n  color-scheme: dark;\n${declarations(darkOnly, "  ")}\n}`,
    `@media (prefers-color-scheme: dark) {\n  :root:not([data-theme="light"]) {\n    color-scheme: dark;\n${declarations(darkOnly, "    ")}\n  }\n}`,
  ];
  return `${blocks.join("\n\n")}\n`;
}
```

- [ ] **Step 8: Write the build entry points**

`packages/tokens/src/build.ts`:

```ts
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { validator } from "@pulseai/contracts";
import { z } from "zod";
import { renderCss } from "./css.ts";
import { ENGINE_TOKENS_DIR, readLayers, TokenError } from "./layers.ts";
import {
  applyOverrides,
  extensionOf,
  findToken,
  leaves,
  missingSectionToken,
  type SectionColor,
  type ThemeOverrides,
} from "./overrides.ts";
import { MODES, type Mode, type ResolvedTokens, resolveMode } from "./resolve.ts";

export interface BuildTokensOptions {
  /** Engine token directory; defaults to the repository's tokens/. */
  engineDir?: string;
  /** Instance directory; its tokens/ folder overrides the engine's, file by file and key by key. */
  instanceDir?: string | undefined;
  preset: string;
  overrides?: ThemeOverrides | undefined;
  sections: readonly SectionColor[];
}

export interface TokenBuild {
  resolved: Record<Mode, ResolvedTokens>;
  css: string;
  /** Fontsource packages the resolved font families need, sorted. */
  fonts: string[];
}

export const CSS_FILE = "tokens.css";

export function modeFile(mode: Mode): string {
  return `${mode}.json`;
}

export async function buildTokens(options: BuildTokensOptions): Promise<TokenBuild> {
  const engineDir = options.engineDir ?? ENGINE_TOKENS_DIR;
  const resolved: Partial<Record<Mode, ResolvedTokens>> = {};
  const fonts = new Set<string>();
  for (const mode of MODES) {
    const layered = readLayers({
      engineDir,
      instanceDir: options.instanceDir,
      preset: options.preset,
      mode,
      modes: MODES,
    });
    const tree = applyOverrides(layered, options.overrides ?? {}, options.sections);
    for (const section of options.sections) {
      if (findToken(tree, section.color_token) === undefined) {
        throw new TokenError(`${mode}: ${missingSectionToken(section)}`);
      }
    }
    for (const { token } of leaves(tree)) {
      const pkg = extensionOf(token)?.fontsource;
      if (typeof pkg === "string") fonts.add(pkg);
    }
    resolved[mode] = await resolveMode(tree, options.preset, mode);
  }
  const complete = resolved as Record<Mode, ResolvedTokens>;
  return { resolved: complete, css: renderCss(complete), fonts: [...fonts].sort() };
}

export function writeTokenBuild(build: TokenBuild, outDir: string): void {
  mkdirSync(outDir, { recursive: true });
  writeFileSync(join(outDir, CSS_FILE), build.css);
  for (const mode of MODES) {
    writeFileSync(
      join(outDir, modeFile(mode)),
      `${JSON.stringify(build.resolved[mode], null, 2)}\n`,
    );
  }
}

const resolvedValidator = validator("tokens-resolved");

/** Read and validate one mode's resolved tokens from a build directory. */
export function readResolved(dir: string, mode: Mode): ResolvedTokens {
  const path = join(dir, modeFile(mode));
  let data: unknown;
  try {
    data = JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    throw new TokenError(`${path}: cannot read resolved tokens (${(error as Error).message})`);
  }
  const result = resolvedValidator.safeParse(data);
  if (!result.success) {
    throw new TokenError(`${path}: invalid resolved tokens\n${z.prettifyError(result.error)}`);
  }
  return data as ResolvedTokens;
}
```

`packages/tokens/src/index.ts`:

```ts
export {
  type BuildTokensOptions,
  buildTokens,
  CSS_FILE,
  modeFile,
  readResolved,
  type TokenBuild,
  writeTokenBuild,
} from "./build.ts";
export { renderCss } from "./css.ts";
export {
  ENGINE_TOKENS_DIR,
  layerFiles,
  mergeTokens,
  presetNames,
  TokenError,
  type TokenTree,
} from "./layers.ts";
export { applyOverrides, EXTENSION, type SectionColor, type ThemeOverrides } from "./overrides.ts";
export {
  CSS_PREFIX,
  MODES,
  type Mode,
  type ResolvedToken,
  type ResolvedTokens,
  resolveMode,
  token,
} from "./resolve.ts";
```

- [ ] **Step 9: Run the tests**

Run: `pnpm --filter @pulseai/tokens test && pnpm --filter @pulseai/tokens typecheck && pnpm --filter @pulseai/contracts test`
Expected: 13 tests pass in `@pulseai/tokens`, typecheck is clean, and the contracts tests pass (including `generated types are current`).

- [ ] **Step 10: Lint and commit**

```bash
uv run ruff format . && uv run ruff check . && pnpm biome check --write tokens schema packages/tokens packages/contracts
git add schema/tokens-resolved.schema.json tokens packages/tokens packages/cli/src/pulseai/models packages/contracts/src/generated pnpm-lock.yaml
git commit -m "feat(tokens): add DTCG design tokens and the @pulseai/tokens build

Three presets (pulse, paper, terminal) in light and dark, layered engine ->
instance -> config overrides and resolved with Style Dictionary into CSS
custom properties and per-mode token maps (tokens-resolved.schema.json).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 6: `pulse tokens check` — the contrast and colour-separation gate

**Files:**
- Modify: `schema/config.schema.json` (`QualityConfig.cvd_simulations`), `defaults/pulse.config.yaml`
- Create: `packages/cli/src/pulseai/tokens/__init__.py`, `packages/cli/src/pulseai/tokens/check.py`
- Create: `packages/cli/tests/token_fixtures.py`, `packages/cli/tests/test_tokens_check.py`
- Modify: `packages/cli/src/pulseai/cli.py` (new `tokens` group), `packages/cli/tests/test_exit_codes.py`, `packages/cli/pyproject.toml` and `uv.lock` (ColorAide)
- Create: `packages/tokens/scripts/check-presets.ts`
- Modify: root `package.json` (script `tokens:check`)
- Regenerate: `packages/cli/src/pulseai/models/config.py`, `packages/contracts/src/generated/config.ts`

**Interfaces:**
- Consumes: resolved token maps (Task 5), `WORK_DIR` (Task 3), `load_config`, `load_registry`, `validate_document`, `load_schema`, `Issue`/`unusable_issue` (M1).
- Produces:
  - `pulseai.tokens.check.check_tokens(tokens_dir: Path, instance_dir: Path | None) -> list[Issue]`, plus `default_tokens_dir(instance_dir)` (`<instance or cwd>/.pulse/tokens`) and `TokenFileError`.
  - CLI `pulse tokens check [--instance DIR] [--tokens DIR]`: exit 0 prints `Design tokens pass.`, 1 on errors, 2 when a map is missing or invalid.
  - Config key `quality.cvd_simulations` (default `[protan, deutan]`, the same pair the dataviz validator gates on; `tritan` is allowed).
  - Script `node packages/tokens/scripts/check-presets.ts --context <file> --out <dir>` (CI gate over every engine preset), and root script `pnpm tokens:check`.
- Rules, per mode:
  1. Every `contrast_against` target exists and reaches `quality.text_contrast_min` (WCAG 2.1).
  2. The sections registry's color tokens exist, and every pair has OKLab ΔE×100 ≥ `section_delta_e_min`.
  3. The same ΔE rule applies to every declared `distinct` set: neighbours only when every member has an `order`, otherwise every pair.
  4. Under each `cvd_simulations` filter, ΔE below `section_cvd_fail` is an error and below `section_cvd_target` a warning.

- [ ] **Step 1: Add the CVD simulation setting**

In `schema/config.schema.json`, add `"cvd_simulations"` to `QualityConfig.required` and to its `properties`:

```json
        "cvd_simulations": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": { "enum": ["protan", "deutan", "tritan"] },
          "description": "Color-vision-deficiency simulations applied to distinct color sets (ColorAide filter names)."
        }
```

In `defaults/pulse.config.yaml`, under `quality:` after `section_cvd_target: 8`, add:

```yaml
  cvd_simulations: [protan, deutan]
```

Run: `uv run python scripts/generate_models.py && pnpm --filter @pulseai/contracts generate`
Expected: `models/config.py` and `generated/config.ts` gain `cvd_simulations`.

- [ ] **Step 2: Write the test fixtures and the failing tests**

`packages/cli/tests/token_fixtures.py`:

```python
"""Resolved token maps for tests: a theme that passes `pulse tokens check`, for tests to break."""

import copy
import json
from pathlib import Path
from typing import Any

SECTIONS = ("models", "tooling", "research", "oss")
SECTION_COLORS = {
    "light": ("#2a78d6", "#eb6834", "#1baf7a", "#eda100"),
    "dark": ("#3987e5", "#d95926", "#199e70", "#e6b000"),
}
SURFACE = {"light": "#ffffff", "dark": "#111111"}
TEXT = {"light": "#111111", "dark": "#f5f5f5"}
CHART = {"light": ("#2a78d6", "#eb6834", "#1baf7a"), "dark": ("#3987e5", "#d95926", "#199e70")}


def entry(path: str, value: Any, extensions: dict[str, Any] | None = None) -> dict[str, Any]:
    token: dict[str, Any] = {
        "value": value,
        "type": "color",
        "name": "--pulse-" + path.replace(".", "-").replace("_", "-"),
    }
    if extensions:
        token["extensions"] = extensions
    return token


def passing(mode: str) -> dict[str, Any]:
    tokens = {
        "color.surface.page": entry("color.surface.page", SURFACE[mode]),
        "color.text.primary": entry(
            "color.text.primary", TEXT[mode], {"contrast_against": ["color.surface.page"]}
        ),
    }
    for section, color in zip(SECTIONS, SECTION_COLORS[mode], strict=True):
        path = f"color.section.{section}"
        tokens[path] = entry(path, color)
    for order, color in enumerate(CHART[mode], start=1):
        path = f"color.chart.category.{order}"
        tokens[path] = entry(path, color, {"distinct": {"set": "chart", "order": order}})
    return {"schema_version": 1, "preset": "test", "mode": mode, "tokens": tokens}


def write(directory: Path, docs: dict[str, dict[str, Any]] | None = None) -> Path:
    """Write light.json and dark.json (passing maps unless docs replaces one)."""
    directory.mkdir(parents=True, exist_ok=True)
    for mode in ("light", "dark"):
        doc = copy.deepcopy((docs or {}).get(mode) or passing(mode))
        (directory / f"{mode}.json").write_text(json.dumps(doc), encoding="utf-8")
    return directory
```

`packages/cli/tests/test_tokens_check.py`:

```python
from pathlib import Path
from typing import Any

from token_fixtures import entry, passing, write
from typer.testing import CliRunner

from pulseai.cli import app
from pulseai.issues import Issue, is_unusable
from pulseai.tokens.check import check_tokens, default_tokens_dir

runner = CliRunner()


def _messages(issues: list[Issue], level: str = "error") -> list[str]:
    return [f"{i.where}: {i.message}" for i in issues if i.level == level]


def _with(mode: str, **values: Any) -> dict[str, Any]:
    doc = passing(mode)
    for path, value in values.items():
        doc["tokens"][path.replace("__", ".")]["value"] = value
    return doc


def test_a_passing_theme_has_no_issues(tmp_path: Path) -> None:
    assert check_tokens(write(tmp_path)) == []


def test_default_tokens_dir_is_in_the_work_dir(tmp_path: Path) -> None:
    assert default_tokens_dir(tmp_path) == tmp_path / ".pulse" / "tokens"


def test_low_text_contrast_is_an_error(tmp_path: Path) -> None:
    doc = _with("light", color__text__primary="#9a9a9a")
    messages = _messages(check_tokens(write(tmp_path, {"light": doc})))
    assert messages == [
        "light/color.text.primary: contrast 2.81:1 against color.surface.page is below 4.5:1"
    ]


def test_a_missing_contrast_target_is_an_error(tmp_path: Path) -> None:
    doc = passing("dark")
    del doc["tokens"]["color.surface.page"]
    messages = _messages(check_tokens(write(tmp_path, {"dark": doc})))
    assert (
        "dark/color.text.primary: contrast target 'color.surface.page' is not defined" in messages
    )


def test_similar_section_colors_are_an_error(tmp_path: Path) -> None:
    doc = _with("light", color__section__tooling="#2f7fd9")
    messages = _messages(check_tokens(write(tmp_path, {"light": doc})))
    assert any(
        m.startswith(
            "light/sections: color.section.models and color.section.tooling are too similar"
        )
        for m in messages
    ), messages


def test_a_section_without_a_color_token_is_an_error(tmp_path: Path) -> None:
    doc = passing("light")
    del doc["tokens"]["color.section.oss"]
    messages = _messages(check_tokens(write(tmp_path, {"light": doc})))
    assert (
        "light/sections: section 'oss' color token 'color.section.oss' is not defined" in messages
    )


def test_colors_that_collapse_under_a_cvd_simulation_are_an_error(tmp_path: Path) -> None:
    doc = _with("light", color__chart__category__1="#d03b3b", color__chart__category__2="#5f8f00")
    messages = _messages(check_tokens(write(tmp_path, {"light": doc})))
    assert any("under deutan simulation" in m for m in messages), messages


def test_colors_in_the_cvd_warning_band_are_a_warning(tmp_path: Path) -> None:
    doc = _with("light", color__chart__category__1="#1baf7a", color__chart__category__2="#e34948")
    issues = check_tokens(write(tmp_path, {"light": doc}))
    assert _messages(issues) == []
    assert any("pair them with labels or patterns" in m for m in _messages(issues, "warning"))


def test_an_ordered_set_compares_neighbours_only(tmp_path: Path) -> None:
    # Slots 1 and 3 are identical, but only neighbours are ever on screen together.
    doc = _with("light", color__chart__category__3="#2a78d6")
    assert check_tokens(write(tmp_path, {"light": doc})) == []
    del doc["tokens"]["color.chart.category.3"]["extensions"]["distinct"]["order"]
    messages = _messages(check_tokens(write(tmp_path, {"light": doc})))
    assert any("color.chart.category.1 and color.chart.category.3" in m for m in messages)


def test_cvd_simulations_come_from_the_config(tmp_path: Path) -> None:
    instance = tmp_path / "instance"
    instance.mkdir()
    (instance / "pulse.config.yaml").write_text(
        "quality:\n  cvd_simulations: [protan]\n", encoding="utf-8"
    )
    doc = _with(
        "light",
        color__chart__category__1="#d03b3b",
        color__chart__category__2="#5f8f00",
        color__chart__category__3="#4a3aa7",
    )
    assert check_tokens(write(tmp_path / "tokens", {"light": doc}), instance) == []


def test_a_missing_token_map_is_unusable(tmp_path: Path) -> None:
    issues = check_tokens(tmp_path / "nowhere")
    assert is_unusable(issues)
    assert "light.json: not found; build the site first" in issues[0].message


def test_a_map_that_fails_its_schema_is_unusable(tmp_path: Path) -> None:
    doc = passing("light")
    doc["tokens"]["color.surface.page"]["name"] = "not-a-css-variable"
    issues = check_tokens(write(tmp_path, {"light": doc}))
    assert is_unusable(issues)
    assert "not a resolved token map" in issues[0].message


def test_a_map_for_the_wrong_mode_is_unusable(tmp_path: Path) -> None:
    issues = check_tokens(write(tmp_path, {"light": passing("dark")}))
    assert is_unusable(issues)
    assert "holds the 'dark' mode, expected 'light'" in issues[0].message


def test_cli_passes_and_fails(tmp_path: Path) -> None:
    good = write(tmp_path / "good")
    result = runner.invoke(app, ["tokens", "check", "--tokens", str(good)])
    assert result.exit_code == 0, result.output
    assert "Design tokens pass." in result.stdout
    bad = write(tmp_path / "bad", {"dark": _with("dark", color__text__primary="#222222")})
    result = runner.invoke(app, ["tokens", "check", "--tokens", str(bad)])
    assert result.exit_code == 1
    assert "dark/color.text.primary: contrast" in result.stderr


def test_entry_names_follow_the_css_prefix() -> None:
    assert entry("color.text.primary", "#000000")["name"] == "--pulse-color-text-primary"
```

In `packages/cli/tests/test_exit_codes.py`, import the fixture writer with the third-party imports (Ruff sorts it there):

```python
from token_fixtures import write as write_tokens
```

Add this helper after `_args`:

```python
def _tokens_args(setup: Setup) -> list[str]:
    tokens = write_tokens(setup.instance / ".pulse" / "tokens")
    return ["tokens", "check", "--tokens", str(tokens), "--instance", str(setup.instance)]
```

Insert this entry into `COMMANDS` after `"site context"`:

```python
    "tokens check": (
        _tokens_args,
        {
            VALID: Expect(0, "stdout", "Design tokens pass."),
            BROKEN_CONFIG: Expect(2, "stderr", "schedule/time"),
            NO_ENGINE_DATA: Expect(2, "stderr", ENGINE_DATA_ENV),
            BROKEN_CATALOG: Expect(2, "stderr", "registries.yaml"),
            BROKEN_SECTIONS: Expect(2, "stderr", "taxonomy/sections.yaml"),
        },
    ),
```

Run: `uv run pytest packages/cli/tests/test_tokens_check.py packages/cli/tests/test_exit_codes.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'pulseai.tokens'`.

- [ ] **Step 3: Add ColorAide and write the check**

Run: `uv add --package pulseai coloraide`

`packages/cli/src/pulseai/tokens/__init__.py`:

```python
"""Design-token checks (the resolved maps come from @pulseai/tokens)."""
```

`packages/cli/src/pulseai/tokens/check.py`:

```python
"""Design-token gate: text contrast and distinguishable colors in every theme mode.

Reads the resolved token maps @pulseai/tokens writes (<instance>/.pulse/tokens/<mode>.json), the
sections registry (each section's color token), and the thresholds in config.quality. Values come
from those files; this module holds only the rules.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from coloraide import Color

from pulseai.config import load_config
from pulseai.issues import Issue, unusable_issue
from pulseai.models.config import PulseConfig
from pulseai.registry.loader import load_registry
from pulseai.schemas import SCHEMA_PROBLEMS, load_schema, validate_document
from pulseai.site.context import WORK_DIR

RESOLVED_SCHEMA = "tokens-resolved.schema.json"
TOKENS_DIR = "tokens"
SECTION_SET = "sections"
# WCAG 2.1 contrast ratio; OKLab delta E scaled by 100, the unit of the config.quality thresholds.
CONTRAST_METHOD = "wcag21"
DELTA_E_METHOD = "ok"
DELTA_E_SCALE = 100

Member = tuple[str, Any]
Pair = tuple[Member, Member]


class TokenFileError(Exception):
    """A resolved token map is missing, unreadable, or not a resolved token map."""


def default_tokens_dir(instance_dir: Path | None) -> Path:
    return (instance_dir or Path.cwd()) / WORK_DIR / TOKENS_DIR


def _error(where: str, message: str) -> Issue:
    return Issue("error", where, message)


def _modes() -> list[str]:
    try:
        schema = load_schema(RESOLVED_SCHEMA)
    except SCHEMA_PROBLEMS as exc:
        msg = f"cannot use schema {RESOLVED_SCHEMA!r} ({exc})"
        raise TokenFileError(msg) from None
    return list(schema["properties"]["mode"]["enum"])


def _read(path: Path, mode: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        msg = f"{path}: not found; build the site first (it writes the token maps) or pass --tokens"
        raise TokenFileError(msg) from None
    except OSError as exc:
        msg = f"{path}: cannot read ({exc.strerror or type(exc).__name__})"
        raise TokenFileError(msg) from None
    try:
        data: Any = json.loads(text)
    except ValueError as exc:
        msg = f"{path}: {exc}"
        raise TokenFileError(msg) from None
    try:
        errors = validate_document(data, RESOLVED_SCHEMA)
    except SCHEMA_PROBLEMS as exc:
        msg = f"cannot use schema {RESOLVED_SCHEMA!r} ({exc})"
        raise TokenFileError(msg) from None
    if errors:
        lines = "\n".join(f"  - {error}" for error in errors)
        msg = f"{path}: not a resolved token map\n{lines}"
        raise TokenFileError(msg)
    if data["mode"] != mode:
        msg = f"{path}: holds the {data['mode']!r} mode, expected {mode!r}"
        raise TokenFileError(msg)
    return data


def _color(value: Any) -> Color | None:
    if not isinstance(value, str):
        return None
    try:
        return Color(value)
    except ValueError:
        return None


def _delta(a: Color, b: Color, simulation: str | None = None) -> float:
    if simulation is not None:
        a, b = a.filter(simulation), b.filter(simulation)
    return a.delta_e(b, method=DELTA_E_METHOD, scalar=DELTA_E_SCALE)


def _check_contrast(mode: str, tokens: dict[str, Any], cfg: PulseConfig) -> Iterator[Issue]:
    minimum = cfg.quality.text_contrast_min
    for path, token in tokens.items():
        for target in token.get("extensions", {}).get("contrast_against", []):
            where = f"{mode}/{path}"
            other = tokens.get(target)
            if other is None:
                yield _error(where, f"contrast target {target!r} is not defined")
                continue
            fg, bg = _color(token["value"]), _color(other["value"])
            if fg is None or bg is None:
                yield _error(where, f"cannot compare {token['value']!r} with {target}: not a color")
                continue
            ratio = fg.contrast(bg, method=CONTRAST_METHOD)
            if ratio < minimum:
                yield _error(where, f"contrast {ratio:.2f}:1 against {target} is below {minimum}:1")


def _check_pairs(mode: str, name: str, pairs: list[Pair], cfg: PulseConfig) -> Iterator[Issue]:
    quality = cfg.quality
    where = f"{mode}/{name}"
    for (a_path, a_value), (b_path, b_value) in pairs:
        a, b = _color(a_value), _color(b_value)
        if a is None or b is None:
            yield _error(where, f"{a_path} and {b_path} must both be colors")
            continue
        normal = _delta(a, b)
        if normal < quality.section_delta_e_min:
            yield _error(
                where,
                f"{a_path} and {b_path} are too similar "
                f"(delta E {normal:.1f}, minimum {quality.section_delta_e_min})",
            )
        for simulation in quality.cvd_simulations:
            simulated = _delta(a, b, simulation)
            if simulated < quality.section_cvd_fail:
                yield _error(
                    where,
                    f"{a_path} and {b_path} are too similar under {simulation} simulation "
                    f"(delta E {simulated:.1f}, minimum {quality.section_cvd_fail})",
                )
            elif simulated < quality.section_cvd_target:
                yield Issue(
                    "warning",
                    where,
                    f"{a_path} and {b_path} are close under {simulation} simulation "
                    f"(delta E {simulated:.1f}, target {quality.section_cvd_target}); "
                    "pair them with labels or patterns",
                )


def _declared_sets(tokens: dict[str, Any]) -> dict[str, list[tuple[int | None, str, Any]]]:
    sets: dict[str, list[tuple[int | None, str, Any]]] = {}
    for path, token in tokens.items():
        distinct = token.get("extensions", {}).get("distinct")
        if distinct is not None:
            member = (distinct.get("order"), path, token["value"])
            sets.setdefault(distinct["set"], []).append(member)
    return sets


def _set_pairs(members: list[tuple[int | None, str, Any]]) -> list[Pair]:
    """Neighbours when every member has an order (a categorical sequence), else every pair."""
    orders = [order for order, _, _ in members]
    if all(order is not None for order in orders):
        ordered = sorted(members, key=lambda member: member[0] or 0)
        return [((a[1], a[2]), (b[1], b[2])) for a, b in itertools.pairwise(ordered)]
    plain = [(path, value) for _, path, value in members]
    return list(itertools.combinations(plain, 2))


def _check_mode(
    mode: str, tokens: dict[str, Any], sections: list[dict[str, Any]], cfg: PulseConfig
) -> Iterator[Issue]:
    yield from _check_contrast(mode, tokens, cfg)
    members: list[Member] = []
    for section in sections:
        token = tokens.get(section["color_token"])
        if token is None:
            yield _error(
                f"{mode}/{SECTION_SET}",
                f"section {section['id']!r} color token {section['color_token']!r} is not defined",
            )
        else:
            members.append((section["color_token"], token["value"]))
    yield from _check_pairs(mode, SECTION_SET, list(itertools.combinations(members, 2)), cfg)
    for name, declared in sorted(_declared_sets(tokens).items()):
        yield from _check_pairs(mode, name, _set_pairs(declared), cfg)


def check_tokens(tokens_dir: Path, instance_dir: Path | None = None) -> list[Issue]:
    """Every contrast and distinctness problem in the resolved token maps under tokens_dir."""
    cfg = load_config(instance_dir)
    sections = load_registry("sections", instance_dir).data["sections"]
    issues: list[Issue] = []
    try:
        maps = {mode: _read(tokens_dir / f"{mode}.json", mode) for mode in _modes()}
    except TokenFileError as exc:
        return [unusable_issue("tokens", str(exc))]
    for mode, doc in maps.items():
        issues += _check_mode(mode, doc["tokens"], sections, cfg)
    return sorted(issues)
```

- [ ] **Step 4: Add the CLI command**

In `packages/cli/src/pulseai/cli.py`, add the import after the `pulseai.site.context` import:

```python
from pulseai.tokens.check import check_tokens, default_tokens_dir
```

and append after the `site` commands:

```python
tokens_app = typer.Typer(help="Check design tokens.", no_args_is_help=True)
app.add_typer(tokens_app, name="tokens")

TokensDirOption = Annotated[
    Path | None,
    typer.Option(
        "--tokens",
        help="Directory with the resolved token maps. Defaults to <instance>/.pulse/tokens.",
        file_okay=False,
        resolve_path=True,
    ),
]


@tokens_app.command("check")
@unusable_input_exits
def tokens_check(instance: InstanceOption = None, tokens: TokensDirOption = None) -> None:
    """Check resolved design tokens: text contrast and distinguishable color sets in every mode."""
    instance_dir = resolve_instance(instance)
    exit_for(check_tokens(tokens or default_tokens_dir(instance_dir), instance_dir))
    typer.echo("Design tokens pass.")
```

- [ ] **Step 5: Run the Python tests**

Run: `uv run ruff format . && uv run ruff check . && uv run pyright && uv run pytest -q`
Expected: all tests pass (the suite grows by the 15 token-check tests and 5 exit-code cases).

- [ ] **Step 6: Gate every engine preset**

`packages/tokens/scripts/check-presets.ts`:

```ts
/**
 * Build every engine theme preset and run `pulse tokens check` on each: the CI gate for the presets
 * the engine ships. Section colors come from a site context file (`pulse site context`).
 *
 *   node packages/tokens/scripts/check-presets.ts --context <site-context.json> --out <dir>
 */
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { validator } from "@pulseai/contracts";
import {
  buildTokens,
  ENGINE_TOKENS_DIR,
  MODES,
  presetNames,
  type SectionColor,
  writeTokenBuild,
} from "../src/index.ts";

const USAGE = "usage: node packages/tokens/scripts/check-presets.ts --context <file> --out <dir>";

const { values } = parseArgs({ options: { context: { type: "string" }, out: { type: "string" } } });
if (values.context === undefined || values.out === undefined) {
  console.error(USAGE);
  process.exit(2);
}
const context: unknown = JSON.parse(readFileSync(values.context, "utf8"));
if (!validator("site-context").safeParse(context).success) {
  console.error(`${values.context}: not a site context; run "pulse site context" first`);
  process.exit(2);
}
const { sections } = context as { sections: SectionColor[] };

const failed: string[] = [];
for (const preset of presetNames([ENGINE_TOKENS_DIR], MODES)) {
  const dir = resolve(values.out, preset);
  writeTokenBuild(await buildTokens({ preset, sections }), dir);
  console.log(`== ${preset}`);
  const result = spawnSync("uv", ["run", "pulse", "tokens", "check", "--tokens", dir], {
    stdio: "inherit",
  });
  if (result.status !== 0) failed.push(preset);
}
if (failed.length > 0) {
  console.error(`presets failing the token check: ${failed.join(", ")}`);
  process.exitCode = 1;
}
```

Add to the root `package.json` `scripts`:

```json
    "tokens:check": "uv run pulse site context --out .pulse/site-context.json && node packages/tokens/scripts/check-presets.ts --context .pulse/site-context.json --out .pulse/presets"
```

Run: `pnpm tokens:check`
Expected: `== paper`, `== pulse` and `== terminal`, each followed by `Design tokens pass.`, then exit 0.

- [ ] **Step 7: Commit**

```bash
pnpm biome check --write schema packages/tokens package.json packages/contracts
git add schema/config.schema.json defaults/pulse.config.yaml packages/cli packages/contracts/src/generated packages/tokens/scripts package.json uv.lock
git commit -m "feat(cli): add pulse tokens check

Gates resolved design tokens on WCAG text contrast, OKLab delta E between
section colors and declared distinct sets, and CVD separation under the
simulations in quality.cvd_simulations. pnpm tokens:check runs it on every
engine preset.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 7: Site foundation — package, build wrapper, report loader, layout, theme switch

**Files:**
- Create: `packages/site/package.json`, `packages/site/tsconfig.json`, `packages/site/astro.config.ts`, `packages/site/vitest.config.ts`
- Create: `packages/site/scripts/pulse-site.ts`
- Create: `packages/site/src/env.d.ts`, `packages/site/src/content.config.ts`
- Create: `packages/site/src/lib/{setup,context,i18n,format,types,schema-values,theme,theme-data,render,site-data,reports-loader,reports}.ts`
- Create: `packages/site/src/client/{theme,theme-switch}.ts`
- Create: `packages/site/src/styles/global.css`, `packages/site/src/layouts/Base.astro`
- Create: `packages/site/src/components/frame/{SiteHeader,SiteFooter,ThemeSwitch,Badge,EmptyState}.astro`
- Create: `packages/site/src/pages/index.astro` (temporary, replaced in Task 13), `packages/site/src/pages/404.astro`
- Create: `packages/site/test/{fixtures,foundation.test,pulse-site.test}.ts`
- Modify: `locales/en.json`, `locales/tr.json` (every site string), root `package.json` (demo scripts), `pnpm-workspace.yaml`, `biome.json`, `.gitignore`, `.github/workflows/dependency-review.yml`

**Interfaces:**
- Consumes: the site context (Task 3), `buildTokens`/`writeTokenBuild`/`readResolved`/`token`/`MODES` (Task 5), generated types (Task 2), `examples/` (Tasks 3–4).
- Produces (later tasks rely on these exact names):
  - `RenderContext` (`src/lib/render.ts`): `{ t, fmt, lang, engineVersion, config, sections, section(id), itemType(id), detailSchema(itemType), minImpact, enums, cssVar(path), tokenNumber(path), url(path) }`.
  - `enums`: `{ confidence, ring, tier, kind, theme, stats, edition, score }`, read from the schemas.
  - `createRenderContext(context, tokens, base)`.
  - `getSite(): Site` (`src/lib/site-data.ts`): `{ paths, context, location, tokens, theme, ctx }`, loaded once per build from `PULSE_INSTANCE_DIR`.
  - `allReports(): Promise<Report[]>`, newest first.
  - `Translator` `t(key, vars?)` throws `MissingStringError`; `t.or(key, fallback)` serves keys built from data; `humanize(name)`.
  - `Formatters`: `number`, `signed`, `date`, `dateShort`, `dateTime`, `value`.
  - Schema helpers: `enumAt`, `requiredAt`, `rangeAt`.
  - Paths: `sitePaths(dir)`, `siteLocation(url)`, `INSTANCE_ENV`.
  - `jsonForScript(value)`, `THEME_DATA_ID`, `THEME_EVENT`, `THEME_STORAGE_KEY`.
  - `themeData(tokens)` / `vegaConfig` / `mermaidVariables` / `categoryColors`.
  - Report loading: `createReportValidator(context)`, `reportFiles(dir)`, `readReport(entry, validate)`, `reportsLoader()`.
  - Client: `effectiveMode()`, `onModeChange(cb)`, `themeData()`.
  - `Badge` (`tone` is a token path); `Base` (`title`, `description?`, `canonical?`).
  - Test fixtures: `engineContext()`, `engineTokens()`, `testContext(base)`, `sampleReport(date)`, `REPO`, `EXAMPLES`.
  - Wrapper: `node scripts/pulse-site.ts <build|dev|preview|check> --instance <dir> [-- astro args]`. Exit 2 means usage; exit 1 means the context or tokens failed.
- The build reads only the instance directory: `.pulse/site-context.json` and `.pulse/tokens/` in, `dist/` out, and `.pulse/astro-cache/` for Astro's cache.

- [ ] **Step 1: Create the package and install its dependencies**

`packages/site/package.json`:

```json
{
  "name": "@pulseai/site",
  "version": "0.1.0",
  "private": true,
  "description": "PulseAI report site: the Astro frame, per-type deep-dives, and generative visuals",
  "license": "MIT",
  "type": "module",
  "scripts": {
    "build:demo": "node scripts/pulse-site.ts build --instance ../../examples",
    "dev:demo": "node scripts/pulse-site.ts dev --instance ../../examples",
    "preview:demo": "node scripts/pulse-site.ts preview --instance ../../examples",
    "check:demo": "node scripts/pulse-site.ts check --instance ../../examples",
    "typecheck": "tsc -p tsconfig.json",
    "test": "vitest run"
  }
}
```

Run:

```bash
pnpm --filter @pulseai/site add astro @astrojs/check @astrojs/sitemap astro-pagefind zod @fontsource-variable/inter @fontsource-variable/newsreader @fontsource-variable/source-serif-4 @fontsource-variable/jetbrains-mono
pnpm --filter @pulseai/site add @pulseai/contracts @pulseai/tokens --workspace
pnpm --filter @pulseai/site add -D typescript@6 vitest @types/node yaml
```

TypeScript is pinned to the 6.x line here because `@astrojs/check` supports `^5 || ^6`; the rest of the repository stays on 7. Task 17 tells Renovate about it.

Append to `pnpm-workspace.yaml`, because Astro's optional image optimizer (sharp, with LGPL libvips) is never used: images are hotlinked, not copied.

```yaml
# Astro's optional image optimizer (sharp, with LGPL libvips) is not used: the site hotlinks
# images instead of copying them (docs/adr/0002-site-rendering.md).
ignoredOptionalDependencies:
  - sharp
```

Run: `pnpm install` (the lockfile then lists `sharp` under `ignoredOptionalDependencies` only).

`packages/site/tsconfig.json`:

```json
{
  "extends": "astro/tsconfigs/strict",
  "compilerOptions": {
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "types": ["node"]
  },
  "include": [".astro/types.d.ts", "src", "scripts", "test", "e2e", "*.ts"],
  "exclude": ["dist"]
}
```

`packages/site/vitest.config.ts`:

```ts
/// <reference types="vitest/config" />
import { getViteConfig } from "astro/config";

export default getViteConfig({
  test: {
    include: ["test/**/*.test.ts"],
  },
});
```

`packages/site/src/env.d.ts`:

```ts
/// <reference types="astro/client" />

declare module "@pulse-generated/*.css";

// Lets plain tsc type .ts files that import components (the tests); astro check reads .astro files
// itself.
declare module "*.astro" {
  const component: import("astro/runtime/server/index.js").AstroComponentFactory;
  export default component;
}
```

In `biome.json`:
- run `pnpm biome migrate --write`, which turns `"recommended": true` into `"preset": "recommended"`;
- add `"!**/.astro"` to `files.includes`;
- add this override, because Biome cannot see template usage in `.astro` files; `astro check` covers them:

```json
  "overrides": [
    {
      "includes": ["**/*.astro"],
      "linter": {
        "rules": { "correctness": { "noUnusedVariables": "off", "noUnusedImports": "off" } }
      }
    }
  ]
```

Append to `.gitignore`:

```gitignore
packages/site/.astro/
packages/site/playwright-report/
packages/site/test-results/
```

In `.github/workflows/dependency-review.yml`, add `OFL-1.1` to `allow-licenses`, and add this comment line after the existing `pulseai` comment:

```yaml
          # OFL-1.1 above covers the Fontsource font packages the site bundles.
```

- [ ] **Step 2: Write the failing tests**

`packages/site/test/fixtures.ts` builds the context of the engine defaults straight from the registry files, so the site's tests need no Python:

```ts
import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { DEFAULT_SCHEMA_DIR } from "@pulseai/contracts";
import { buildTokens, type Mode, type ResolvedTokens } from "@pulseai/tokens";
import { parse } from "yaml";
import { parseSiteContext, type SiteContext } from "../src/lib/context.ts";
import { createRenderContext, type RenderContext } from "../src/lib/render.ts";
import type { Report } from "../src/lib/types.ts";

export const REPO = resolve(DEFAULT_SCHEMA_DIR, "..");
export const EXAMPLES = join(REPO, "examples");

function read<T>(relative: string): T {
  const text = readFileSync(join(REPO, relative), "utf8");
  return (relative.endsWith(".json") ? JSON.parse(text) : parse(text)) as T;
}

/**
 * The context `pulse site context` writes for the engine defaults (no instance), assembled from
 * the registry files so the site's tests run without Python. Validated like a real context.
 */
export function engineContext(): SiteContext {
  const itemTypes = read<{ item_types: SiteContext["item_types"] }>(
    "taxonomy/item-types.yaml",
  ).item_types;
  const schemas: SiteContext["schemas"] = {
    "report.schema.json": read("schema/report.schema.json"),
  };
  for (const file of readdirSync(join(REPO, "schema/item-types")).sort()) {
    schemas[`item-types/${file}`] = read(`schema/item-types/${file}`);
  }
  const sections = read<{ sections: SiteContext["sections"] }>("taxonomy/sections.yaml").sections;
  const context = {
    schema_version: 1,
    engine_version: "0.0.0-test",
    config: read("defaults/pulse.config.yaml"),
    sections: [...sections].sort((a, b) => a.order - b.order || a.id.localeCompare(b.id)),
    item_types: itemTypes,
    strings: read<{ strings: SiteContext["strings"] }>("locales/en.json").strings,
    schemas,
  };
  return parseSiteContext(context, "engine defaults");
}

let tokens: Promise<Record<Mode, ResolvedTokens>> | undefined;

export function engineTokens(): Promise<Record<Mode, ResolvedTokens>> {
  tokens ??= buildTokens({ preset: "pulse", sections: engineContext().sections }).then(
    (build) => build.resolved,
  );
  return tokens;
}

export async function testContext(base = "/"): Promise<RenderContext> {
  return createRenderContext(engineContext(), await engineTokens(), base);
}

/** A sample edition from examples/ (the showcase is 2026-10-11). */
export function sampleReport(date = "2026-10-11"): Report {
  return JSON.parse(
    readFileSync(join(EXAMPLES, "reports", ...date.split("-"), "report.json"), "utf8"),
  ) as Report;
}
```

`packages/site/test/foundation.test.ts`:

```ts
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { token } from "@pulseai/tokens";
import { describe, expect, it } from "vitest";
import { parseSiteContext, SiteContextError } from "../src/lib/context.ts";
import { createFormatters } from "../src/lib/format.ts";
import { createTranslator, humanize, interpolate, MissingStringError } from "../src/lib/i18n.ts";
import {
  createReportValidator,
  ReportError,
  readReport,
  reportFiles,
} from "../src/lib/reports-loader.ts";
import { enumAt, rangeAt, requiredAt, SchemaValueError } from "../src/lib/schema-values.ts";
import {
  INSTANCE_ENV,
  requireInstanceDir,
  SiteSetupError,
  siteLocation,
  sitePaths,
} from "../src/lib/setup.ts";
import { jsonForScript } from "../src/lib/theme.ts";
import { categoryColors, mermaidVariables, themeData, vegaConfig } from "../src/lib/theme-data.ts";
import { EXAMPLES, engineContext, engineTokens, REPO, sampleReport } from "./fixtures.ts";

const SITE_SRC = join(REPO, "packages/site/src");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { recursive: true, encoding: "utf8" })
    .filter((rel) => rel.endsWith(".astro") || rel.endsWith(".ts") || rel.endsWith(".css"))
    .map((rel) => join(dir, rel));
}

describe("siteLocation", () => {
  it("has no origin and a root base without a site URL", () => {
    expect(siteLocation(null)).toEqual({ base: "/" });
  });

  it("splits a project-site URL into origin and base", () => {
    expect(siteLocation("https://mordris.github.io/PulseAI/")).toEqual({
      site: "https://mordris.github.io",
      base: "/PulseAI/",
    });
  });

  it("adds the trailing slash a base needs", () => {
    expect(siteLocation("https://example.org/reports").base).toBe("/reports/");
    expect(siteLocation("https://example.org").base).toBe("/");
  });
});

describe("site paths", () => {
  it("lays out an instance directory", () => {
    const paths = sitePaths("/srv/instance");
    expect(paths.contextFile).toBe("/srv/instance/.pulse/site-context.json");
    expect(paths.tokensDir).toBe("/srv/instance/.pulse/tokens");
    expect(paths.reportsDir).toBe("/srv/instance/reports");
    expect(paths.outDir).toBe("/srv/instance/dist");
  });

  it("names the wrapper when the instance is not set", () => {
    expect(() => requireInstanceDir({})).toThrow(SiteSetupError);
    expect(() => requireInstanceDir({})).toThrow("scripts/pulse-site.ts build --instance");
    expect(requireInstanceDir({ [INSTANCE_ENV]: "/srv/instance" })).toBe("/srv/instance");
  });
});

describe("translator", () => {
  const t = createTranslator(
    { "ui.hello": "Hello {name}", "ui.count": "{shown} of {total}" },
    "en",
  );

  it("fills placeholders and leaves unknown ones for client code", () => {
    expect(t("ui.hello", { name: "Ada" })).toBe("Hello Ada");
    expect(t("ui.count", { shown: 2 })).toBe("2 of {total}");
    expect(interpolate("{a}{a}", { a: 1 })).toBe("11");
  });

  it("fails on a missing key with the key and language", () => {
    expect(() => t("ui.nope")).toThrow(MissingStringError);
    expect(() => t("ui.nope")).toThrow('missing locale string "ui.nope" for language "en"');
  });

  it("falls back for keys built from data", () => {
    expect(t.or("fields.reading_minutes", humanize("reading_minutes"))).toBe("Reading minutes");
    expect(t.has("ui.hello")).toBe(true);
  });
});

describe("formatters", () => {
  const fmt = createFormatters("en");
  const t = createTranslator(engineContext().strings, "en");

  it("formats calendar dates without shifting the day", () => {
    expect(fmt.date("2026-10-11")).toBe("October 11, 2026");
    expect(fmt.dateShort("2026-10-01")).toBe("Oct 1");
  });

  it("formats timestamps in the report's time zone", () => {
    expect(fmt.dateTime("2026-10-11T14:00:00Z", "Europe/Istanbul")).toBe("Oct 11, 2026, 5:00 PM");
  });

  it("signs changes and formats values of every kind", () => {
    expect(fmt.signed(3)).toBe("+3");
    expect(fmt.signed(-2)).toBe("-2");
    expect(fmt.signed(0)).toBe("0");
    expect(fmt.value(true, t)).toBe("Yes");
    expect(fmt.value(null, t)).toBe("—");
    expect(fmt.value(["a", 1000], t)).toBe("a, 1,000");
  });
});

describe("schema values", () => {
  const schema = {
    properties: { a: { enum: ["x", "y"], required: ["p", "q"], minimum: 1, maximum: 3 } },
  };

  it("reads enums, required lists, and integer ranges", () => {
    expect(enumAt(schema, "properties.a")).toEqual(["x", "y"]);
    expect(requiredAt(schema, "properties.a")).toEqual(["p", "q"]);
    expect(rangeAt(schema, "properties.a")).toEqual([1, 2, 3]);
  });

  it("fails clearly when the schema has no such value", () => {
    expect(() => enumAt(schema, "properties.b")).toThrow(SchemaValueError);
    expect(() => rangeAt(schema, "properties.b")).toThrow("no integer range at properties.b");
  });
});

describe("jsonForScript", () => {
  it("cannot close the script element it lives in", () => {
    const text = jsonForScript({ note: "</script><script>alert(1)</script>" });
    expect(text).not.toContain("</script>");
    expect(JSON.parse(text)).toEqual({ note: "</script><script>alert(1)</script>" });
  });
});

describe("site context", () => {
  it("accepts the context of the engine defaults", () => {
    expect(engineContext().sections.map((section) => section.id)).toEqual([
      "models",
      "tooling",
      "research",
      "oss",
    ]);
  });

  it("names the part of the context that is invalid", () => {
    const context = structuredClone(engineContext()) as unknown as { config: { language: string } };
    context.config.language = "English";
    expect(() => parseSiteContext(context, "ctx.json")).toThrow(SiteContextError);
    expect(() => parseSiteContext(context, "ctx.json")).toThrow("ctx.json: config is invalid");
  });
});

describe("report validation", () => {
  const validate = createReportValidator(engineContext());

  it("accepts every sample edition", () => {
    for (const date of ["2026-10-09", "2026-10-10", "2026-10-11"]) {
      expect(validate(sampleReport(date), date).meta.date).toBe(date);
    }
  });

  it("rejects an unknown section with the file and path", () => {
    const report = sampleReport();
    const first = report.items[0];
    if (first === undefined) throw new Error("fixture changed");
    first.section = "weather";
    expect(() => validate(report, "r.json")).toThrow(ReportError);
    expect(() => validate(report, "r.json")).toThrow(
      'r.json: items/0/section: unknown section "weather"',
    );
  });

  it("checks each item's detail against its type's schema", () => {
    const report = sampleReport();
    const first = report.items[0];
    if (first === undefined) throw new Error("fixture changed");
    (first.detail as { [key: string]: unknown }).org = 42;
    expect(() => validate(report, "r.json")).toThrow("r.json: items/0/detail/org:");
  });

  it("reports schema problems with their paths", () => {
    const report = sampleReport() as unknown as { headline: unknown };
    report.headline = "";
    expect(() => validate(report, "r.json")).toThrow("r.json: headline:");
  });
});

describe("report files", () => {
  it("finds the sample editions oldest first", () => {
    const files = reportFiles(join(EXAMPLES, "reports"));
    expect(files.map((file) => file.date)).toEqual(["2026-10-09", "2026-10-10", "2026-10-11"]);
  });

  it("rejects a report outside reports/YYYY/MM/DD/", () => {
    const dir = mkdtempSync(join(tmpdir(), "pulse-reports-"));
    mkdirSync(join(dir, "drafts"));
    writeFileSync(join(dir, "drafts", "report.json"), "{}");
    expect(() => reportFiles(dir)).toThrow("reports live at reports/YYYY/MM/DD/report.json");
  });

  it("rejects a report filed under another date", () => {
    const dir = mkdtempSync(join(tmpdir(), "pulse-reports-"));
    mkdirSync(join(dir, "2026", "10", "12"), { recursive: true });
    const file = join(dir, "2026", "10", "12", "report.json");
    writeFileSync(file, JSON.stringify(sampleReport()));
    const validate = createReportValidator(engineContext());
    expect(() => readReport({ file, date: "2026-10-12" }, validate)).toThrow(
      "meta.date is 2026-10-11, but the file is filed under 2026-10-12",
    );
  });
});

describe("theme data", () => {
  it("themes charts from tokens in both modes", async () => {
    const tokens = await engineTokens();
    const light = vegaConfig(tokens.light);
    expect((light.range as { category: string[] }).category).toEqual(categoryColors(tokens.light));
    expect(categoryColors(tokens.light)).toHaveLength(8);
    expect(categoryColors(tokens.light)[0]).toBe(
      token(tokens.light, "color.chart.category.1").value,
    );
    expect((light.axis as { gridColor: string }).gridColor).toBe(
      token(tokens.light, "color.chart.grid").value,
    );
    const data = themeData(tokens);
    expect(Object.keys(data.vega)).toEqual(["light", "dark"]);
    expect(data.mermaid.dark.primaryTextColor).toBe(token(tokens.dark, "color.text.primary").value);
    expect(mermaidVariables(tokens.light).fontFamily).toContain("Inter Variable");
  });

  it("orders categorical slots numerically", async () => {
    const tokens = structuredClone((await engineTokens()).light);
    const ten = tokens.tokens["color.chart.category.1"];
    if (ten === undefined) throw new Error("fixture changed");
    tokens.tokens["color.chart.category.10"] = { ...ten, value: "#000000" };
    expect(categoryColors(tokens).at(-1)).toBe("#000000");
  });
});

describe("source rules", () => {
  it("uses only locale strings that exist in every language", () => {
    const keys = new Set<string>();
    for (const file of sourceFiles(SITE_SRC)) {
      for (const match of readFileSync(file, "utf8").matchAll(/\bt\(\s*"([a-z0-9_.-]+)"/g)) {
        if (match[1] !== undefined) keys.add(match[1]);
      }
    }
    expect(keys.size).toBeGreaterThan(0);
    for (const lang of ["en", "tr"]) {
      const strings = JSON.parse(
        readFileSync(join(REPO, "locales", `${lang}.json`), "utf8"),
      ).strings;
      const missing = [...keys].filter((key) => !(key in strings));
      expect(missing, lang).toEqual([]);
    }
  });

  it("has no raw colors outside the token files", () => {
    const raw = /#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab)\(/i;
    const offenders = sourceFiles(SITE_SRC).flatMap((file) =>
      readFileSync(file, "utf8")
        .split("\n")
        .map((line, index) => ({ line, index }))
        .filter(({ line }) => raw.test(line.replace(/href="#[^"]*"|`#\$\{[^}]*\}`|"#"/g, "")))
        .map(({ index }) => `${relative(SITE_SRC, file)}:${index + 1}`),
    );
    expect(offenders).toEqual([]);
  });
});
```

`packages/site/test/pulse-site.test.ts`:

```ts
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";
import { fontImports, main } from "../scripts/pulse-site.ts";

const SITE_DIR = fileURLToPath(new URL("..", import.meta.url));

describe("pulse-site", () => {
  it("exits 2 with usage for a missing command or instance", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(await main([])).toBe(2);
    expect(await main(["build"])).toBe(2);
    expect(await main(["deploy", "--instance", "."])).toBe(2);
    expect(await main(["build", "--nope"])).toBe(2);
    expect(error.mock.calls.flat().join("\n")).toContain("usage: node scripts/pulse-site.ts");
    error.mockRestore();
  });

  it("exits 1 when the instance has no context yet", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const instance = mkdtempSync(join(tmpdir(), "pulse-instance-"));
    expect(await main(["build", "--instance", instance])).toBe(1);
    expect(error.mock.calls.flat().join("\n")).toContain(
      'run "pulse site context --instance <dir>"',
    );
    error.mockRestore();
  });

  it("imports fonts relative to the generated file", () => {
    const css = fontImports(
      ["@fontsource-variable/inter"],
      join(SITE_DIR, ".pulse", "tokens", "fonts.css"),
      [SITE_DIR],
    );
    expect(css).toMatch(/@import "\.\.\/\.\.\/.*@fontsource-variable\/inter\/index\.css";/);
  });

  it("names a font package that is not installed", () => {
    expect(() =>
      fontImports(["@fontsource-variable/nope"], join(SITE_DIR, "fonts.css"), [SITE_DIR]),
    ).toThrow('font package "@fontsource-variable/nope" is not installed');
  });
});
```

Run: `pnpm --filter @pulseai/site test`
Expected: FAIL with `Cannot find module '../src/lib/context.ts'`.

- [ ] **Step 3: Add the site's strings**

Merge these entries into `strings` in `locales/en.json`:

```json
{
  "ui.site.title": "PulseAI",
  "ui.site.description": "A daily, source-checked report on AI and software.",
  "ui.nav.label": "Site",
  "ui.nav.skip": "Skip to content",
  "ui.nav.latest": "Latest",
  "ui.nav.archive": "Archive",
  "ui.nav.feed": "RSS",
  "ui.search.label": "Search reports",
  "ui.search.placeholder": "Search reports",
  "ui.theme.label": "Theme",
  "ui.theme.auto": "Auto",
  "ui.theme.light": "Light",
  "ui.theme.dark": "Dark",
  "ui.footer.generated": "Generated by PulseAI {version}",
  "ui.masthead.edition": "Edition {edition}",
  "ui.masthead.window": "Covers {start} to {end} ({tz})",
  "ui.masthead.sample": "Sample edition",
  "ui.score.label": "Pulse score",
  "ui.score.vs_avg": "{delta} against the 7-day average of {average}",
  "ui.score.no_avg": "No 7-day average yet",
  "ui.delta.up": "Up {value}",
  "ui.delta.down": "Down {value}",
  "ui.delta.flat": "No change",
  "ui.kpis.title": "Key numbers",
  "ui.tldr.title": "TL;DR",
  "ui.front_page.title": "Front page",
  "ui.radar.title": "Adoption radar",
  "ui.actions.title": "What to do next",
  "ui.signals.title": "Signals",
  "ui.signals.intro": "Reported, not yet confirmed by a primary source. Treat these as leads, not facts.",
  "ui.corrections.title": "Corrections",
  "ui.corrections.entry": "Correction to {date}:",
  "ui.methodology.title": "Methodology",
  "ui.methodology.rejected": "Left out",
  "ui.methodology.item": "Item",
  "ui.methodology.reason": "Reason",
  "ui.health.title": "Source health",
  "ui.health.source": "Source",
  "ui.health.status": "Status",
  "ui.health.items": "Items",
  "ui.health.ok": "OK",
  "ui.health.failed": "Failed",
  "ui.funnel.title": "From scanned to published",
  "ui.funnel.alt": "Bar chart of the research funnel: {scanned} scanned, {triaged} triaged, {verified} verified, {published} published",
  "ui.funnel.source": "This run",
  "ui.funnel.stage": "Stage",
  "ui.funnel.count": "Items",
  "ui.run.engine": "Engine",
  "ui.run.host": "Host",
  "ui.run.cost": "Run cost",
  "ui.run.cost_unknown": "Not measured",
  "ui.run.models": "Models",
  "ui.filters.title": "Filter items",
  "ui.filters.section": "Section",
  "ui.filters.type": "Type",
  "ui.filters.min_impact": "Impact",
  "ui.filters.impact_at_least": "{value} or more",
  "ui.filters.confidence": "Confidence",
  "ui.filters.status": "New or update",
  "ui.filters.all": "All",
  "ui.filters.new": "New",
  "ui.filters.updates": "Updates",
  "ui.filters.reset": "Reset",
  "ui.filters.expand_all": "Expand all",
  "ui.filters.collapse_all": "Collapse all",
  "ui.filters.count": "{shown} of {total} items shown",
  "ui.filters.no_match": "No items match these filters.",
  "ui.section.other": "Other",
  "ui.section.notes": "Notes",
  "ui.section.note_link": "Details",
  "ui.item.impact": "Impact {value}/{max}",
  "ui.item.novelty": "Novelty {value}/{max}",
  "ui.item.relevance": "Relevance {value}/{max}",
  "ui.item.update": "Update",
  "ui.item.update_of": "Follows up on the {date} report",
  "ui.item.why": "Why it matters:",
  "ui.item.what_to_do": "What to do:",
  "ui.item.caveats": "Caveats:",
  "ui.item.facts": "Key numbers",
  "ui.item.fact_source": "Source {n}",
  "ui.item.sources": "Sources",
  "ui.item.permalink": "Link to this item",
  "ui.visual.source": "Source: {source}",
  "ui.visual.data": "Show the data",
  "ui.visual.diagram_source": "Show the diagram source",
  "ui.image.credit": "Credit: {credit}",
  "ui.image.license": "License: {license}",
  "ui.table.empty_cell": "—",
  "ui.yes": "Yes",
  "ui.no": "No",
  "ui.format.usd": "${value}",
  "ui.format.usd_per_mtok": "${value} per million tokens",
  "ui.format.tokens": "{value} tokens",
  "ui.release.from": "from {version}",
  "ui.paper.peer_reviewed": "Peer reviewed",
  "ui.paper.preprint": "Preprint",
  "ui.paper.arxiv": "arXiv {id}",
  "ui.paper.not_released": "Not released",
  "ui.paper.minutes": "{minutes} min",
  "ui.article.full_read_yes": "Worth reading in full",
  "ui.article.full_read_no": "The summary is enough",
  "ui.repo.stars_delta": "{delta} stars in the last 7 days ({stars} in total)",
  "ui.advisory.cvss": "CVSS {score}",
  "ui.advisory.exploited": "Exploited in the wild",
  "ui.advisory.not_exploited": "No known exploitation",
  "ui.leaderboard.alt": "Slope chart of rank changes, before and after",
  "ui.leaderboard.rank_axis": "Rank",
  "ui.leaderboard.source": "Leaderboard",
  "ui.archive.title": "Archive",
  "ui.archive.count": "{count} editions",
  "ui.archive.heatmap_title": "Pulse score by day",
  "ui.archive.heatmap_alt": "Calendar heatmap of the daily Pulse score; darker days had more impact",
  "ui.archive.source": "Every edition in this archive",
  "ui.archive.date": "Date",
  "ui.archive.score": "Score {score}",
  "ui.feed.title": "PulseAI daily report",
  "ui.empty.title": "No reports yet",
  "ui.empty.text": "The first edition appears here after the first run.",
  "ui.not_found.title": "Page not found",
  "ui.not_found.text": "There is no page at this address.",
  "ui.not_found.home": "Go to the latest edition",
  "fields.context_tokens": "Context window",
  "fields.price_in_per_mtok": "Input price",
  "fields.price_out_per_mtok": "Output price",
  "fields.modalities": "Modalities",
  "fields.availability": "Availability",
  "fields.weights": "Weights",
  "fields.license": "License",
  "fields.problem": "Problem",
  "fields.key_idea": "Key idea",
  "fields.code_url": "Code",
  "fields.data_url": "Data",
  "fields.weights_url": "Weights",
  "fields.difficulty": "Difficulty",
  "fields.sections": "Read first",
  "fields.author": "Author",
  "fields.language": "Language",
  "fields.stars_delta_7d": "Stars, last 7 days",
  "fields.last_commit": "Last commit",
  "fields.affected": "Affected",
  "fields.fixed_in": "Fixed in",
  "fields.what": "What",
  "fields.amount": "How much",
  "fields.before": "Before",
  "fields.after": "After",
  "rings.adopt": "Adopt",
  "rings.trial": "Trial",
  "rings.assess": "Assess",
  "rings.hold": "Hold",
  "confidence.confirmed": "Confirmed",
  "confidence.reported": "Reported",
  "confidence.rumor": "Rumor",
  "tiers.t1": "Primary source",
  "tiers.t1-data": "Primary data",
  "tiers.t2": "Curator",
  "tiers.t3": "Discovery",
  "kinds.primary": "Primary",
  "kinds.secondary": "Secondary",
  "changelog.new": "New",
  "changelog.fix": "Fix",
  "changelog.breaking": "Breaking",
  "changelog.perf": "Performance",
  "changelog.deprecation": "Deprecation",
  "changelog.security": "Security",
  "severity.low": "Low",
  "severity.medium": "Medium",
  "severity.high": "High",
  "severity.critical": "Critical",
  "difficulty.intro": "Introductory",
  "difficulty.intermediate": "Intermediate",
  "difficulty.advanced": "Advanced",
  "weights.open": "Open weights",
  "weights.closed": "Closed",
  "weights.partial": "Partly open",
  "hosts.routine": "Claude Code routine",
  "hosts.actions": "GitHub Actions",
  "hosts.local": "Local machine",
  "hosts.fixture": "Test fixture",
  "modes.normal": "Regular edition",
  "modes.plain": "Plain edition",
  "modes.catch_up": "Catch-up edition",
  "stats.scanned": "Scanned",
  "stats.triaged": "Triaged",
  "stats.verified": "Verified",
  "stats.published": "Published"
}
```

and these into `locales/tr.json`:

```json
{
  "ui.site.title": "PulseAI",
  "ui.site.description": "Yapay zekâ ve yazılım üzerine kaynakları doğrulanmış günlük rapor.",
  "ui.nav.label": "Site",
  "ui.nav.skip": "İçeriğe geç",
  "ui.nav.latest": "Son rapor",
  "ui.nav.archive": "Arşiv",
  "ui.nav.feed": "RSS",
  "ui.search.label": "Raporlarda ara",
  "ui.search.placeholder": "Raporlarda ara",
  "ui.theme.label": "Tema",
  "ui.theme.auto": "Otomatik",
  "ui.theme.light": "Açık",
  "ui.theme.dark": "Koyu",
  "ui.footer.generated": "PulseAI {version} ile üretildi",
  "ui.masthead.edition": "Sayı {edition}",
  "ui.masthead.window": "{start} ile {end} arasını kapsar ({tz})",
  "ui.masthead.sample": "Örnek sayı",
  "ui.score.label": "Pulse puanı",
  "ui.score.vs_avg": "7 günlük ortalamaya ({average}) göre {delta}",
  "ui.score.no_avg": "Henüz 7 günlük ortalama yok",
  "ui.delta.up": "{value} artış",
  "ui.delta.down": "{value} düşüş",
  "ui.delta.flat": "Değişiklik yok",
  "ui.kpis.title": "Önemli rakamlar",
  "ui.tldr.title": "Kısaca",
  "ui.front_page.title": "Ön sayfa",
  "ui.radar.title": "Benimseme radarı",
  "ui.actions.title": "Sıradaki adımlar",
  "ui.signals.title": "Sinyaller",
  "ui.signals.intro": "Haber olarak geçti ama birincil kaynakla doğrulanmadı. Bunları gerçek değil, ipucu olarak değerlendirin.",
  "ui.corrections.title": "Düzeltmeler",
  "ui.corrections.entry": "{date} tarihli rapora düzeltme:",
  "ui.methodology.title": "Yöntem",
  "ui.methodology.rejected": "Dışarıda bırakılanlar",
  "ui.methodology.item": "Öğe",
  "ui.methodology.reason": "Neden",
  "ui.health.title": "Kaynak durumu",
  "ui.health.source": "Kaynak",
  "ui.health.status": "Durum",
  "ui.health.items": "Öğe",
  "ui.health.ok": "Çalışıyor",
  "ui.health.failed": "Hata",
  "ui.funnel.title": "Taramadan yayına",
  "ui.funnel.alt": "Araştırma hunisinin çubuk grafiği: {scanned} tarandı, {triaged} elendi, {verified} doğrulandı, {published} yayımlandı",
  "ui.funnel.source": "Bu çalışma",
  "ui.funnel.stage": "Aşama",
  "ui.funnel.count": "Öğe",
  "ui.run.engine": "Motor",
  "ui.run.host": "Çalıştığı yer",
  "ui.run.cost": "Çalışma maliyeti",
  "ui.run.cost_unknown": "Ölçülmedi",
  "ui.run.models": "Modeller",
  "ui.filters.title": "Öğeleri süz",
  "ui.filters.section": "Bölüm",
  "ui.filters.type": "Tür",
  "ui.filters.min_impact": "Etki",
  "ui.filters.impact_at_least": "{value} ve üstü",
  "ui.filters.confidence": "Güven",
  "ui.filters.status": "Yeni ya da güncelleme",
  "ui.filters.all": "Tümü",
  "ui.filters.new": "Yeni",
  "ui.filters.updates": "Güncellemeler",
  "ui.filters.reset": "Sıfırla",
  "ui.filters.expand_all": "Tümünü aç",
  "ui.filters.collapse_all": "Tümünü kapat",
  "ui.filters.count": "{total} öğeden {shown} tanesi gösteriliyor",
  "ui.filters.no_match": "Bu süzgeçlere uyan öğe yok.",
  "ui.section.other": "Diğer",
  "ui.section.notes": "Notlar",
  "ui.section.note_link": "Ayrıntılar",
  "ui.item.impact": "Etki {value}/{max}",
  "ui.item.novelty": "Yenilik {value}/{max}",
  "ui.item.relevance": "İlgi {value}/{max}",
  "ui.item.update": "Güncelleme",
  "ui.item.update_of": "{date} tarihli raporun devamı",
  "ui.item.why": "Neden önemli:",
  "ui.item.what_to_do": "Ne yapmalı:",
  "ui.item.caveats": "Dikkat:",
  "ui.item.facts": "Önemli rakamlar",
  "ui.item.fact_source": "Kaynak {n}",
  "ui.item.sources": "Kaynaklar",
  "ui.item.permalink": "Bu öğenin bağlantısı",
  "ui.visual.source": "Kaynak: {source}",
  "ui.visual.data": "Verileri göster",
  "ui.visual.diagram_source": "Diyagram kaynağını göster",
  "ui.image.credit": "Görsel: {credit}",
  "ui.image.license": "Lisans: {license}",
  "ui.table.empty_cell": "—",
  "ui.yes": "Evet",
  "ui.no": "Hayır",
  "ui.format.usd": "{value} $",
  "ui.format.usd_per_mtok": "Milyon token başına {value} $",
  "ui.format.tokens": "{value} token",
  "ui.release.from": "önceki sürüm {version}",
  "ui.paper.peer_reviewed": "Hakemli",
  "ui.paper.preprint": "Ön baskı",
  "ui.paper.arxiv": "arXiv {id}",
  "ui.paper.not_released": "Yayımlanmadı",
  "ui.paper.minutes": "{minutes} dk",
  "ui.article.full_read_yes": "Tamamını okumaya değer",
  "ui.article.full_read_no": "Özet yeterli",
  "ui.repo.stars_delta": "Son 7 günde {delta} yıldız (toplam {stars})",
  "ui.advisory.cvss": "CVSS {score}",
  "ui.advisory.exploited": "Aktif olarak istismar ediliyor",
  "ui.advisory.not_exploited": "Bilinen istismar yok",
  "ui.leaderboard.alt": "Sıralama değişikliklerinin önce ve sonra eğim grafiği",
  "ui.leaderboard.rank_axis": "Sıra",
  "ui.leaderboard.source": "Sıralama tablosu",
  "ui.archive.title": "Arşiv",
  "ui.archive.count": "{count} sayı",
  "ui.archive.heatmap_title": "Günlere göre Pulse puanı",
  "ui.archive.heatmap_alt": "Günlük Pulse puanının takvim ısı haritası; koyu günler daha etkili",
  "ui.archive.source": "Bu arşivdeki tüm sayılar",
  "ui.archive.date": "Tarih",
  "ui.archive.score": "Puan {score}",
  "ui.feed.title": "PulseAI günlük rapor",
  "ui.empty.title": "Henüz rapor yok",
  "ui.empty.text": "İlk sayı, ilk çalışmadan sonra burada görünür.",
  "ui.not_found.title": "Sayfa bulunamadı",
  "ui.not_found.text": "Bu adreste bir sayfa yok.",
  "ui.not_found.home": "Son sayıya git",
  "fields.context_tokens": "Bağlam penceresi",
  "fields.price_in_per_mtok": "Girdi fiyatı",
  "fields.price_out_per_mtok": "Çıktı fiyatı",
  "fields.modalities": "Kipler",
  "fields.availability": "Erişim",
  "fields.weights": "Ağırlıklar",
  "fields.license": "Lisans",
  "fields.problem": "Problem",
  "fields.key_idea": "Ana fikir",
  "fields.code_url": "Kod",
  "fields.data_url": "Veri",
  "fields.weights_url": "Ağırlıklar",
  "fields.difficulty": "Zorluk",
  "fields.sections": "Önce okuyun",
  "fields.author": "Yazar",
  "fields.language": "Dil",
  "fields.stars_delta_7d": "Son 7 günde yıldız",
  "fields.last_commit": "Son commit",
  "fields.affected": "Etkilenen",
  "fields.fixed_in": "Düzeltildiği sürüm",
  "fields.what": "Ne",
  "fields.amount": "Ne kadar",
  "fields.before": "Önce",
  "fields.after": "Sonra",
  "rings.adopt": "Benimse",
  "rings.trial": "Dene",
  "rings.assess": "Değerlendir",
  "rings.hold": "Bekle",
  "confidence.confirmed": "Doğrulandı",
  "confidence.reported": "Haber",
  "confidence.rumor": "Söylenti",
  "tiers.t1": "Birincil kaynak",
  "tiers.t1-data": "Birincil veri",
  "tiers.t2": "Derleyici",
  "tiers.t3": "Keşif",
  "kinds.primary": "Birincil",
  "kinds.secondary": "İkincil",
  "changelog.new": "Yeni",
  "changelog.fix": "Düzeltme",
  "changelog.breaking": "Uyumsuz değişiklik",
  "changelog.perf": "Performans",
  "changelog.deprecation": "Kullanımdan kaldırma",
  "changelog.security": "Güvenlik",
  "severity.low": "Düşük",
  "severity.medium": "Orta",
  "severity.high": "Yüksek",
  "severity.critical": "Kritik",
  "difficulty.intro": "Giriş",
  "difficulty.intermediate": "Orta",
  "difficulty.advanced": "İleri",
  "weights.open": "Açık ağırlıklar",
  "weights.closed": "Kapalı",
  "weights.partial": "Kısmen açık",
  "hosts.routine": "Claude Code rutini",
  "hosts.actions": "GitHub Actions",
  "hosts.local": "Yerel makine",
  "hosts.fixture": "Test verisi",
  "modes.normal": "Normal sayı",
  "modes.plain": "Sade sayı",
  "modes.catch_up": "Telafi sayısı",
  "stats.scanned": "Tarandı",
  "stats.triaged": "Elendi",
  "stats.verified": "Doğrulandı",
  "stats.published": "Yayımlandı"
}
```

- [ ] **Step 4: Write the library modules**

`packages/site/src/lib/setup.ts`:

```ts
import { join, resolve } from "node:path";

/** The instance directory the build reads (set by scripts/pulse-site.ts). */
export const INSTANCE_ENV = "PULSE_INSTANCE_DIR";

// Layout of an instance directory. WORK_DIR, CONTEXT_FILE and TOKENS_DIR must match the CLI
// (pulseai.site.context and pulseai.tokens.check), which writes and reads the same files.
export const WORK_DIR = ".pulse";
export const CONTEXT_FILE = "site-context.json";
export const TOKENS_DIR = "tokens";
export const CACHE_DIR = "astro-cache";
export const REPORTS_DIR = "reports";
export const OUT_DIR = "dist";

export class SiteSetupError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SiteSetupError";
  }
}

export interface SitePaths {
  instanceDir: string;
  workDir: string;
  contextFile: string;
  tokensDir: string;
  cacheDir: string;
  reportsDir: string;
  outDir: string;
}

export function sitePaths(instanceDir: string): SitePaths {
  const root = resolve(instanceDir);
  const workDir = join(root, WORK_DIR);
  return {
    instanceDir: root,
    workDir,
    contextFile: join(workDir, CONTEXT_FILE),
    tokensDir: join(workDir, TOKENS_DIR),
    cacheDir: join(workDir, CACHE_DIR),
    reportsDir: join(root, REPORTS_DIR),
    outDir: join(root, OUT_DIR),
  };
}

/** The instance directory from the environment, or undefined (unit tests render without one). */
export function instanceDirFromEnv(env: NodeJS.ProcessEnv = process.env): string | undefined {
  const value = env[INSTANCE_ENV];
  return value ? resolve(value) : undefined;
}

export function requireInstanceDir(env: NodeJS.ProcessEnv = process.env): string {
  const dir = instanceDirFromEnv(env);
  if (dir === undefined) {
    throw new SiteSetupError(
      `${INSTANCE_ENV} is not set; build with "node scripts/pulse-site.ts build --instance <dir>"`,
    );
  }
  return dir;
}

export interface SiteLocation {
  /** Origin for absolute URLs (feeds, sitemap); absent when config.site.url is null. */
  site?: string;
  /** Path prefix of every page, with leading and trailing slashes. */
  base: string;
}

/** Split config.site.url into Astro's `site` (origin) and `base` (path). */
export function siteLocation(url: string | null | undefined): SiteLocation {
  if (!url) return { base: "/" };
  const parsed = new URL(url);
  const base = parsed.pathname.endsWith("/") ? parsed.pathname : `${parsed.pathname}/`;
  return { site: parsed.origin, base };
}
```

`packages/site/src/lib/context.ts`:

```ts
import { readFileSync } from "node:fs";
import {
  type ConfigSchema,
  type ItemTypesSchema,
  type JsonSchema,
  type SectionsSchema,
  validator,
} from "@pulseai/contracts";
import { z } from "zod";

export type PulseConfig = ConfigSchema.PulseConfig;
export type Section = SectionsSchema.Section;
export type SectionGroup = SectionsSchema.SectionGroup;
export type ItemType = ItemTypesSchema.ItemType;

/** The bundle `pulse site context` writes (schema/site-context.schema.json), with typed parts. */
export interface SiteContext {
  schema_version: 1;
  engine_version: string;
  config: PulseConfig;
  sections: Section[];
  item_types: ItemType[];
  strings: { [key: string]: string };
  schemas: { [name: string]: JsonSchema };
}

export class SiteContextError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SiteContextError";
  }
}

/** Validate a parsed context: the bundle shape, then each nested document with its own schema. */
export function parseSiteContext(data: unknown, source: string): SiteContext {
  const bundle = validator("site-context").safeParse(data);
  if (!bundle.success) {
    throw new SiteContextError(`${source}: not a site context\n${z.prettifyError(bundle.error)}`);
  }
  const doc = data as SiteContext;
  const parts: [string, string, unknown][] = [
    ["config", "config", doc.config],
    ["sections", "sections", { schema_version: 1, sections: doc.sections }],
    ["item_types", "item-types", { schema_version: 1, item_types: doc.item_types }],
  ];
  for (const [field, schema, value] of parts) {
    const result = validator(schema).safeParse(value);
    if (!result.success) {
      throw new SiteContextError(
        `${source}: ${field} is invalid\n${z.prettifyError(result.error)}`,
      );
    }
  }
  return doc;
}

export function loadSiteContext(file: string): SiteContext {
  let text: string;
  try {
    text = readFileSync(file, "utf8");
  } catch {
    throw new SiteContextError(
      `${file}: not found; run "pulse site context --instance <dir>" before building the site`,
    );
  }
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (error) {
    throw new SiteContextError(`${file}: ${(error as Error).message}`);
  }
  return parseSiteContext(data, file);
}
```

`packages/site/src/lib/i18n.ts`:

```ts
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
```

`packages/site/src/lib/format.ts`:

```ts
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
  const formatters: Formatters = {
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
      if (Array.isArray(value)) return value.map((entry) => formatters.value(entry, t)).join(", ");
      if (typeof value === "object") return JSON.stringify(value);
      return String(value);
    },
  };
  return formatters;
}
```

`packages/site/src/lib/types.ts`:

```ts
import type { ReportSchema } from "@pulseai/contracts";

export type Report = ReportSchema.Report;
export type Item = ReportSchema.Item;
export type ItemSource = ReportSchema.ItemSource;
export type ItemFact = ReportSchema.ItemFact;
export type ItemImage = ReportSchema.ItemImage;
export type Kpi = ReportSchema.Kpi;
export type Visual = ReportSchema.Visual;
export type LeafVisual = ReportSchema.LeafVisual;
export type VegaLiteVisual = ReportSchema.VegaLiteVisual;
export type MermaidVisual = ReportSchema.MermaidVisual;
export type TableVisual = ReportSchema.TableVisual;
export type ImageRefVisual = ReportSchema.ImageRefVisual;
export type DashboardVisual = ReportSchema.DashboardVisual;
export type StatTile = ReportSchema.StatTile;
export type VisualTile = ReportSchema.VisualTile;
export type RadarEntry = ReportSchema.RadarEntry;
export type SectionNote = ReportSchema.SectionNote;
export type RunStats = ReportSchema.RunStats;
```

`packages/site/src/lib/schema-values.ts`:

```ts
import type { JsonSchema } from "@pulseai/contracts";

export class SchemaValueError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SchemaValueError";
  }
}

function at(schema: JsonSchema, path: string): unknown {
  let node: unknown = schema;
  for (const key of path.split(".")) {
    if (node === null || typeof node !== "object") return undefined;
    node = (node as { [key: string]: unknown })[key];
  }
  return node;
}

/** The `enum` list at a dotted path of a schema: option lists come from schemas, not code. */
export function enumAt(schema: JsonSchema, path: string): string[] {
  const values = at(schema, `${path}.enum`);
  if (!Array.isArray(values) || !values.every((value) => typeof value === "string")) {
    throw new SchemaValueError(`no string enum at ${path}`);
  }
  return values;
}

/** The `required` list at a dotted path (its order is the schema author's field order). */
export function requiredAt(schema: JsonSchema, path: string): string[] {
  const values = at(schema, `${path}.required`);
  if (!Array.isArray(values) || !values.every((value) => typeof value === "string")) {
    throw new SchemaValueError(`no required list at ${path}`);
  }
  return values;
}

/** Every integer from `minimum` to `maximum` at a dotted path. */
export function rangeAt(schema: JsonSchema, path: string): number[] {
  const low = at(schema, `${path}.minimum`);
  const high = at(schema, `${path}.maximum`);
  if (typeof low !== "number" || typeof high !== "number" || low > high) {
    throw new SchemaValueError(`no integer range at ${path}`);
  }
  return Array.from({ length: high - low + 1 }, (_, index) => low + index);
}

/** Report enums the frame renders as options, in schema order. */
export interface ReportEnums {
  confidence: string[];
  ring: string[];
  tier: string[];
  kind: string[];
  theme: string[];
  stats: string[];
  /** Edition modes; the schema lists the regular edition first. */
  edition: string[];
  /** The impact/novelty/relevance scale, lowest first. */
  score: number[];
}

export function reportEnums(report: JsonSchema, config: JsonSchema): ReportEnums {
  return {
    confidence: enumAt(report, "$defs.item.properties.confidence"),
    ring: enumAt(report, "$defs.radarEntry.properties.ring"),
    tier: enumAt(report, "$defs.source.properties.tier"),
    kind: enumAt(report, "$defs.source.properties.kind"),
    theme: enumAt(config, "properties.theme.properties.default"),
    stats: requiredAt(report, "$defs.meta.properties.stats"),
    edition: enumAt(report, "$defs.meta.properties.mode"),
    score: rangeAt(report, "$defs.score"),
  };
}
```

`packages/site/src/lib/theme.ts`:

```ts
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
```

`packages/site/src/lib/theme-data.ts`:

```ts
import { MODES, type Mode, type ResolvedTokens, token } from "@pulseai/tokens";

/** Prefix of the categorical chart palette; slots are numbered from 1 in token order. */
const CATEGORY_PREFIX = "color.chart.category.";

/** Chart and diagram themes for both modes, built from resolved tokens and inlined in each page. */
export interface ThemeData {
  vega: Record<Mode, VegaConfig>;
  mermaid: Record<Mode, MermaidVariables>;
}

export type VegaConfig = { [key: string]: unknown };
export interface MermaidVariables {
  fontFamily: string;
  [key: string]: string;
}

function text(tokens: ResolvedTokens, path: string): string {
  return String(token(tokens, path).value);
}

function num(tokens: ResolvedTokens, path: string): number {
  const value = token(tokens, path).value;
  const parsed = typeof value === "number" ? value : Number.parseFloat(value);
  if (Number.isNaN(parsed)) throw new Error(`token "${path}" is not a number`);
  return parsed;
}

/** The categorical palette in slot order. */
export function categoryColors(tokens: ResolvedTokens): string[] {
  return Object.keys(tokens.tokens)
    .filter((path) => path.startsWith(CATEGORY_PREFIX))
    .sort(
      (a, b) => Number(a.slice(CATEGORY_PREFIX.length)) - Number(b.slice(CATEGORY_PREFIX.length)),
    )
    .map((path) => text(tokens, path));
}

/** A Vega-Lite config: chrome, palette, and mark defaults from tokens; reports never set colors. */
export function vegaConfig(tokens: ResolvedTokens): VegaConfig {
  const font = text(tokens, "font.family.body");
  const label = text(tokens, "color.chart.label");
  const axis = text(tokens, "color.chart.axis");
  const labelSize = num(tokens, "chart.label_size");
  const category = categoryColors(tokens);
  const ramp = [text(tokens, "color.chart.ramp.low"), text(tokens, "color.chart.ramp.high")];
  return {
    background: "transparent",
    font,
    padding: 4,
    view: { stroke: "transparent", continuousHeight: num(tokens, "chart.height") },
    axis: {
      domainColor: axis,
      tickColor: axis,
      gridColor: text(tokens, "color.chart.grid"),
      labelColor: label,
      titleColor: label,
      labelFont: font,
      titleFont: font,
      labelFontSize: labelSize,
      titleFontSize: labelSize,
      titleFontWeight: num(tokens, "font.weight.medium"),
    },
    // Horizontal category labels read best; Vega-Lite drops overlapping ones.
    axisX: { labelAngle: 0, labelOverlap: true },
    legend: {
      labelColor: label,
      titleColor: label,
      labelFont: font,
      titleFont: font,
      labelFontSize: labelSize,
      titleFontSize: labelSize,
    },
    header: { labelColor: label, titleColor: label, labelFont: font, titleFont: font },
    title: {
      color: text(tokens, "color.text.primary"),
      font,
      fontSize: num(tokens, "chart.title_size"),
    },
    range: { category, ramp, heatmap: ramp, ordinal: ramp },
    mark: { color: category[0] },
    bar: { cornerRadiusEnd: num(tokens, "chart.bar_corner_radius") },
    line: { strokeWidth: num(tokens, "chart.line_width") },
    point: { size: num(tokens, "chart.point_size"), filled: true },
    rule: { color: axis },
    text: { color: text(tokens, "color.text.secondary"), font, fontSize: labelSize },
  };
}

/** Mermaid "base" theme variables from tokens. */
export function mermaidVariables(tokens: ResolvedTokens): MermaidVariables {
  const raised = text(tokens, "color.surface.raised");
  const sunken = text(tokens, "color.surface.sunken");
  const primary = text(tokens, "color.text.primary");
  return {
    fontFamily: text(tokens, "font.family.body"),
    background: raised,
    mainBkg: sunken,
    primaryColor: sunken,
    primaryTextColor: primary,
    primaryBorderColor: text(tokens, "color.accent.default"),
    secondaryColor: raised,
    tertiaryColor: text(tokens, "color.surface.page"),
    textColor: primary,
    titleColor: primary,
    lineColor: text(tokens, "color.text.secondary"),
    nodeBorder: text(tokens, "color.border.strong"),
    clusterBkg: text(tokens, "color.surface.page"),
    clusterBorder: text(tokens, "color.border.subtle"),
    edgeLabelBackground: raised,
    noteBkgColor: sunken,
    noteTextColor: primary,
  };
}

export function themeData(tokens: Record<Mode, ResolvedTokens>): ThemeData {
  const vega = {} as Record<Mode, VegaConfig>;
  const mermaid = {} as Record<Mode, MermaidVariables>;
  for (const mode of MODES) {
    vega[mode] = vegaConfig(tokens[mode]);
    mermaid[mode] = mermaidVariables(tokens[mode]);
  }
  return { vega, mermaid };
}
```

`packages/site/src/lib/render.ts`:

```ts
import { getSchema, type JsonSchema } from "@pulseai/contracts";
import { type Mode, type ResolvedTokens, token } from "@pulseai/tokens";
import type { ItemType, PulseConfig, Section, SiteContext } from "./context.ts";
import { createFormatters, type Formatters } from "./format.ts";
import { createTranslator, type Translator } from "./i18n.ts";
import { type ReportEnums, reportEnums } from "./schema-values.ts";

const REPORT_SCHEMA = "report.schema.json";
const ITEM_TYPE_SCHEMA_DIR = "item-types";

/** What every component needs to render: strings, formats, registries, tokens, and links. */
export interface RenderContext {
  t: Translator;
  fmt: Formatters;
  lang: string;
  engineVersion: string;
  config: PulseConfig;
  /** Sections in registry order. */
  sections: readonly Section[];
  section(id: string): Section | undefined;
  itemType(id: string): ItemType | undefined;
  /** The detail schema of an item type, as the context resolved it. */
  detailSchema(itemType: ItemType): JsonSchema;
  minImpact: number;
  enums: ReportEnums;
  /** `var(--pulse-…)` for a token path; throws when no theme defines it. */
  cssVar(path: string): string;
  /** A numeric token (chart sizes); throws when it is missing or not a number. */
  tokenNumber(path: string): number;
  /** A link below the site's base path: url("2026/10/11/") -> "/PulseAI/2026/10/11/". */
  url(path: string): string;
}

export class RenderContextError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RenderContextError";
  }
}

export function createRenderContext(
  context: SiteContext,
  tokens: Record<Mode, ResolvedTokens>,
  base: string,
): RenderContext {
  const lang = context.config.language;
  const sections = new Map(context.sections.map((section) => [section.id, section]));
  const itemTypes = new Map(context.item_types.map((itemType) => [itemType.id, itemType]));
  const schema = (name: string): JsonSchema => {
    const found = context.schemas[name];
    if (found === undefined) throw new RenderContextError(`the site context has no ${name}`);
    return found;
  };
  return {
    t: createTranslator(context.strings, lang),
    fmt: createFormatters(lang),
    lang,
    engineVersion: context.engine_version,
    config: context.config,
    sections: context.sections,
    section: (id) => sections.get(id),
    itemType: (id) => itemTypes.get(id),
    detailSchema: (itemType) => schema(`${ITEM_TYPE_SCHEMA_DIR}/${itemType.schema}`),
    minImpact: context.config.deep_dive.min_impact,
    // The theme choices are an engine contract (config.schema.json ships with @pulseai/contracts).
    enums: reportEnums(schema(REPORT_SCHEMA), getSchema("config")),
    cssVar: (path) => `var(${token(tokens.light, path).name})`,
    tokenNumber: (path) => {
      const value = token(tokens.light, path).value;
      if (typeof value !== "number")
        throw new RenderContextError(`token "${path}" is not a number`);
      return value;
    },
    url: (path) => `${base}${path.replace(/^\/+/, "")}`,
  };
}
```

`packages/site/src/lib/site-data.ts`:

```ts
import { MODES, type Mode, type ResolvedTokens, readResolved } from "@pulseai/tokens";
import { loadSiteContext, type SiteContext } from "./context.ts";
import { createRenderContext, type RenderContext } from "./render.ts";
import {
  requireInstanceDir,
  type SiteLocation,
  type SitePaths,
  siteLocation,
  sitePaths,
} from "./setup.ts";
import { type ThemeData, themeData } from "./theme-data.ts";

/** Everything a page needs at build time, loaded once per build from the instance directory. */
export interface Site {
  paths: SitePaths;
  context: SiteContext;
  location: SiteLocation;
  tokens: Record<Mode, ResolvedTokens>;
  theme: ThemeData;
  ctx: RenderContext;
}

let cached: Site | undefined;

export function getSite(): Site {
  if (cached !== undefined) return cached;
  const paths = sitePaths(requireInstanceDir());
  const context = loadSiteContext(paths.contextFile);
  const tokens = Object.fromEntries(
    MODES.map((mode) => [mode, readResolved(paths.tokensDir, mode)]),
  ) as Record<Mode, ResolvedTokens>;
  const location = siteLocation(context.config.site.url);
  cached = {
    paths,
    context,
    location,
    tokens,
    theme: themeData(tokens),
    ctx: createRenderContext(context, tokens, location.base),
  };
  return cached;
}
```

`packages/site/src/lib/reports-loader.ts`:

```ts
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { compile } from "@pulseai/contracts";
import type { Loader } from "astro/loaders";
import type { z } from "zod";
import { loadSiteContext, type SiteContext } from "./context.ts";
import { requireInstanceDir, sitePaths } from "./setup.ts";
import type { Report } from "./types.ts";

const REPORT_SCHEMA = "report.schema.json";
const ITEM_TYPE_SCHEMA_DIR = "item-types";
const REPORT_FILE = "report.json";
/** reports/YYYY/MM/DD/report.json, relative to the reports directory. */
const REPORT_PATH = /^(\d{4})[/\\](\d{2})[/\\](\d{2})[/\\]report\.json$/;

export class ReportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ReportError";
  }
}

function describeIssues(error: z.ZodError, file: string, prefix: string[] = []): string[] {
  return error.issues.map((issue) => {
    const path = [...prefix, ...issue.path.map(String)].join("/") || "<root>";
    return `${file}: ${path}: ${issue.message}`;
  });
}

export type ReportValidator = (data: unknown, file: string) => Report;

/**
 * Validate reports with the context's schemas: the report schema, each item's detail schema, and
 * the registry references the frame needs to render (section and item type). The remaining
 * cross-reference rules belong to `pulse validate`, which runs before a report is published.
 */
export function createReportValidator(context: SiteContext): ReportValidator {
  const reportSchema = context.schemas[REPORT_SCHEMA];
  if (reportSchema === undefined) throw new ReportError(`the site context has no ${REPORT_SCHEMA}`);
  const report = compile(reportSchema);
  const sections = new Set(context.sections.map((section) => section.id));
  const details = new Map(
    context.item_types.map((itemType) => {
      const name = `${ITEM_TYPE_SCHEMA_DIR}/${itemType.schema}`;
      const schema = context.schemas[name];
      if (schema === undefined) throw new ReportError(`the site context has no ${name}`);
      return [itemType.id, compile(schema)] as const;
    }),
  );
  return (data, file) => {
    const parsed = report.safeParse(data);
    if (!parsed.success) throw new ReportError(describeIssues(parsed.error, file).join("\n"));
    const doc = data as Report;
    const problems: string[] = [];
    for (const key of ["items", "signals"] as const) {
      doc[key].forEach((item, index) => {
        const where = `${key}/${index}`;
        if (!sections.has(item.section)) {
          problems.push(`${file}: ${where}/section: unknown section "${item.section}"`);
        }
        const detail = details.get(item.type);
        if (detail === undefined) {
          problems.push(`${file}: ${where}/type: unknown item type "${item.type}"`);
          return;
        }
        const result = detail.safeParse(item.detail);
        if (!result.success)
          problems.push(...describeIssues(result.error, file, [where, "detail"]));
      });
    }
    if (problems.length > 0) throw new ReportError(problems.join("\n"));
    return doc;
  };
}

export interface ReportFile {
  file: string;
  /** The date the path names, YYYY-MM-DD. */
  date: string;
}

/** Every report.json below dir, oldest first; one in the wrong place is an error. */
export function reportFiles(dir: string): ReportFile[] {
  let entries: string[];
  try {
    entries = readdirSync(dir, { recursive: true, encoding: "utf8" });
  } catch {
    return [];
  }
  const files: ReportFile[] = [];
  for (const rel of entries) {
    if (!rel.endsWith(REPORT_FILE)) continue;
    const match = REPORT_PATH.exec(rel);
    if (match === null) {
      throw new ReportError(`${join(dir, rel)}: reports live at reports/YYYY/MM/DD/report.json`);
    }
    files.push({ file: join(dir, rel), date: `${match[1]}-${match[2]}-${match[3]}` });
  }
  return files.sort((a, b) => a.date.localeCompare(b.date));
}

export function readReport(entry: ReportFile, validate: ReportValidator): Report {
  let data: unknown;
  try {
    data = JSON.parse(readFileSync(entry.file, "utf8"));
  } catch (error) {
    throw new ReportError(`${entry.file}: ${(error as Error).message}`);
  }
  const report = validate(data, entry.file);
  if (report.meta.date !== entry.date) {
    throw new ReportError(
      `${entry.file}: meta.date is ${report.meta.date}, but the file is filed under ${entry.date}`,
    );
  }
  return report;
}

/** The content loader: every report of the instance, validated, keyed by date. */
export function reportsLoader(): Loader {
  return {
    name: "pulse-reports",
    async load({ store, logger, generateDigest }) {
      const paths = sitePaths(requireInstanceDir());
      const validate = createReportValidator(loadSiteContext(paths.contextFile));
      store.clear();
      const files = reportFiles(paths.reportsDir);
      for (const entry of files) {
        const report = readReport(entry, validate);
        const data = report as unknown as Record<string, unknown>;
        store.set({ id: entry.date, data, digest: generateDigest(data) });
      }
      logger.info(`loaded ${files.length} reports from ${paths.reportsDir}`);
    },
  };
}
```

`packages/site/src/lib/reports.ts`:

```ts
import { getCollection } from "astro:content";
import type { Report } from "./types.ts";

/** Every report of the instance, newest first. */
export async function allReports(): Promise<Report[]> {
  // Typed by hand so this also type-checks before `astro sync` has generated content types.
  const entries: { data: unknown }[] = await getCollection("reports");
  return entries
    .map((entry) => entry.data as Report)
    .sort((a: Report, b: Report) => b.meta.date.localeCompare(a.meta.date));
}
```

- [ ] **Step 5: Write the build wrapper and the Astro configuration**

`packages/site/scripts/pulse-site.ts`:

```ts
#!/usr/bin/env node
/**
 * Build, serve, preview, or type-check the site for an instance directory.
 *
 *   node scripts/pulse-site.ts <build|dev|preview|check> --instance <dir> [-- <astro arguments>]
 *
 * build, dev, and check first resolve the design tokens (engine, instance, config overrides) into
 * <instance>/.pulse/tokens/ with the font imports. Every command then runs Astro with
 * PULSE_INSTANCE_DIR set. The context must exist: run `pulse site context --instance <dir>` first.
 */
import { spawnSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { buildTokens, writeTokenBuild } from "@pulseai/tokens";
import { loadSiteContext } from "../src/lib/context.ts";
import { INSTANCE_ENV, sitePaths } from "../src/lib/setup.ts";

export const FONTS_FILE = "fonts.css";
const COMMANDS = ["build", "dev", "preview", "check"];
const TOKEN_COMMANDS = ["build", "dev", "check"];
const SITE_DIR = fileURLToPath(new URL("..", import.meta.url));
const USAGE = `usage: node scripts/pulse-site.ts <${COMMANDS.join("|")}> --instance <dir> [-- <astro args>]`;

/** The CSS entry of a font package, looked up from each directory in turn. */
function resolveFont(pkg: string, searchFrom: readonly string[]): string {
  for (const dir of searchFrom) {
    try {
      return createRequire(join(dir, "package.json")).resolve(pkg);
    } catch {
      // Not installed here; try the next directory.
    }
  }
  throw new Error(`font package "${pkg}" is not installed; add it to the instance's package.json`);
}

/** @import rules for the font packages, relative to the generated file so Vite can follow them. */
export function fontImports(
  packages: readonly string[],
  cssFile: string,
  searchFrom: readonly string[],
): string {
  const lines = packages.map((pkg) => {
    const path = relative(dirname(cssFile), resolveFont(pkg, searchFrom)).split(sep).join("/");
    return `@import "${path.startsWith(".") ? path : `./${path}`}";`;
  });
  return `/* Generated by @pulseai/site from the font tokens. Do not edit. */\n${lines.join("\n")}\n`;
}

/** Resolve the tokens and font imports an instance's build reads. */
export async function prepare(instanceDir: string): Promise<void> {
  const paths = sitePaths(instanceDir);
  const context = loadSiteContext(paths.contextFile);
  const build = await buildTokens({
    instanceDir: paths.instanceDir,
    preset: context.config.theme.preset,
    overrides: context.config.theme.overrides,
    sections: context.sections,
  });
  writeTokenBuild(build, paths.tokensDir);
  const fontsFile = join(paths.tokensDir, FONTS_FILE);
  writeFileSync(fontsFile, fontImports(build.fonts, fontsFile, [SITE_DIR, paths.instanceDir]));
}

function astroBin(): string {
  const require = createRequire(import.meta.url);
  const manifest = require("astro/package.json") as { bin: string | { [name: string]: string } };
  const bin = typeof manifest.bin === "string" ? manifest.bin : manifest.bin.astro;
  if (bin === undefined) throw new Error("the astro package declares no astro binary");
  return join(dirname(require.resolve("astro/package.json")), bin);
}

export async function main(argv: string[]): Promise<number> {
  let parsed: ReturnType<typeof parseArgs>;
  try {
    parsed = parseArgs({
      args: argv,
      allowPositionals: true,
      options: { instance: { type: "string" } },
    });
  } catch (error) {
    console.error(`${(error as Error).message}\n${USAGE}`);
    return 2;
  }
  const [command, ...astroArgs] = parsed.positionals;
  const instance = parsed.values.instance;
  if (command === undefined || !COMMANDS.includes(command) || typeof instance !== "string") {
    console.error(USAGE);
    return 2;
  }
  const instanceDir = resolve(instance);
  try {
    if (TOKEN_COMMANDS.includes(command)) await prepare(instanceDir);
  } catch (error) {
    console.error((error as Error).message);
    return 1;
  }
  const result = spawnSync(process.execPath, [astroBin(), command, ...astroArgs], {
    cwd: SITE_DIR,
    stdio: "inherit",
    env: { ...process.env, [INSTANCE_ENV]: instanceDir },
  });
  return result.status ?? 1;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}
```

`packages/site/astro.config.ts`:

```ts
import { createRequire } from "node:module";
import { sep } from "node:path";
import { fileURLToPath } from "node:url";
import sitemap from "@astrojs/sitemap";
import { defineConfig, passthroughImageService } from "astro/config";
import pagefind from "astro-pagefind";
import { loadSiteContext } from "./src/lib/context.ts";
import { instanceDirFromEnv, siteLocation, sitePaths } from "./src/lib/setup.ts";

// Unit tests load this file without an instance; builds always have one (scripts/pulse-site.ts).
const instanceDir = instanceDirFromEnv();
const paths = instanceDir === undefined ? undefined : sitePaths(instanceDir);
const context = paths === undefined ? undefined : loadSiteContext(paths.contextFile);
const location = siteLocation(context?.config.site.url);
const siteDir = fileURLToPath(new URL(".", import.meta.url));

/** The directory that holds node_modules for the installed packages (instance or engine repo). */
function modulesRoot(): string {
  const astro = createRequire(import.meta.url).resolve("astro/package.json");
  const marker = `${sep}node_modules${sep}`;
  return astro.slice(0, astro.indexOf(marker));
}

export default defineConfig({
  output: "static",
  trailingSlash: "always",
  build: { format: "directory" },
  // Images are hotlinked, never optimized or copied (see Figure.astro).
  image: { service: passthroughImageService() },
  base: location.base,
  ...(location.site === undefined ? {} : { site: location.site }),
  ...(paths === undefined ? {} : { outDir: paths.outDir, cacheDir: paths.cacheDir }),
  integrations: [
    ...(context?.config.site.search ? [pagefind()] : []),
    ...(location.site === undefined ? [] : [sitemap()]),
  ],
  vite: {
    ...(paths === undefined
      ? {}
      : {
          resolve: { alias: { "@pulse-generated": paths.workDir } },
          server: { fs: { allow: [siteDir, paths.instanceDir, modulesRoot()] } },
        }),
  },
});
```

`packages/site/src/content.config.ts`:

```ts
import { defineCollection } from "astro:content";
import { reportsLoader } from "./lib/reports-loader.ts";

export const collections = {
  reports: defineCollection({ loader: reportsLoader() }),
};
```

- [ ] **Step 6: Write the layout, the theme switch, and the first pages**

`packages/site/src/styles/global.css`:

```css
/* The frame's base styles. Every value comes from a design token (--pulse-*). */

*,
*::before,
*::after {
  box-sizing: border-box;
}

html {
  background: var(--pulse-color-surface-page);
  color: var(--pulse-color-text-primary);
  font-family: var(--pulse-font-family-body);
  font-size: 100%;
  line-height: var(--pulse-font-line-height-normal);
  -webkit-text-size-adjust: 100%;
  text-size-adjust: 100%;
  scroll-padding-top: var(--pulse-space-6);
}

body {
  margin: 0;
  min-height: 100vh;
  background: var(--pulse-color-surface-page);
  font-size: var(--pulse-font-size-md);
}

[hidden] {
  /* biome-ignore lint/complexity/noImportantStyles: hidden must beat any component display rule */
  display: none !important;
}

a {
  color: var(--pulse-color-accent-default);
  text-decoration-thickness: var(--pulse-border-width-thin);
  text-underline-offset: 0.18em;
}

a:hover {
  text-decoration-thickness: var(--pulse-border-width-thick);
}

:focus-visible {
  outline: var(--pulse-border-width-thick) solid var(--pulse-color-focus-ring);
  outline-offset: var(--pulse-border-width-thick);
  border-radius: var(--pulse-radius-sm);
}

h1,
h2,
h3,
h4 {
  margin: 0;
  font-family: var(--pulse-font-family-display);
  font-weight: var(--pulse-font-weight-semibold);
  line-height: var(--pulse-font-line-height-tight);
  text-wrap: balance;
  overflow-wrap: anywhere;
}

p,
ul,
ol,
dl,
figure,
blockquote {
  margin: 0;
}

p,
li,
dd {
  text-wrap: pretty;
  overflow-wrap: break-word;
}

img,
svg {
  max-width: 100%;
}

code,
pre,
kbd {
  font-family: var(--pulse-font-family-mono);
  font-size: var(--pulse-font-size-sm);
  /* Code is copied: show ">=" as typed, never as a ligature. */
  font-variant-ligatures: none;
}

pre {
  margin: 0;
  padding: var(--pulse-space-3) var(--pulse-space-4);
  overflow-x: auto;
  background: var(--pulse-color-surface-sunken);
  border: var(--pulse-border-width-thin) solid var(--pulse-color-border-subtle);
  border-radius: var(--pulse-radius-md);
  line-height: var(--pulse-font-line-height-normal);
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}

.skip-link {
  position: absolute;
  inset-inline-start: var(--pulse-space-4);
  inset-block-start: var(--pulse-space-2);
  z-index: 10;
  padding: var(--pulse-space-2) var(--pulse-space-4);
  background: var(--pulse-color-surface-raised);
  border: var(--pulse-border-width-thin) solid var(--pulse-color-border-strong);
  border-radius: var(--pulse-radius-md);
  transform: translateY(-200%);
}

.skip-link:focus {
  transform: none;
}

.page {
  width: 100%;
  max-width: var(--pulse-layout-content-width);
  margin-inline: auto;
  padding-inline: var(--pulse-space-4);
}

@media (min-width: 48rem) {
  .page {
    padding-inline: var(--pulse-space-6);
  }
}

.flow > * + * {
  margin-block-start: var(--pulse-space-4);
}

.region {
  margin-block: var(--pulse-space-7);
}

.region__title {
  margin-block-end: var(--pulse-space-4);
  font-size: var(--pulse-font-size-xl);
}

.prose {
  max-width: var(--pulse-layout-reading-width);
}

.muted {
  color: var(--pulse-color-text-secondary);
}

/* Small labels: badges carry a tone (a semantic color token) as a dot plus a tinted ground. */
.badge {
  display: inline-flex;
  align-items: center;
  gap: var(--pulse-space-1);
  padding: 0 var(--pulse-space-2);
  border: var(--pulse-border-width-thin) solid var(--pulse-color-border-strong);
  border-radius: var(--pulse-radius-pill);
  background: var(--pulse-color-surface-raised);
  color: var(--pulse-color-text-secondary);
  font-family: var(--pulse-font-family-body);
  font-size: var(--pulse-font-size-xs);
  font-weight: var(--pulse-font-weight-medium);
  line-height: var(--pulse-font-line-height-normal);
  white-space: nowrap;
}

.badge[data-tone] {
  border-color: color-mix(in oklab, var(--tone) 55%, var(--pulse-color-border-strong));
  background: color-mix(in oklab, var(--tone) 14%, var(--pulse-color-surface-raised));
  color: var(--pulse-color-text-primary);
}

.badge[data-tone]::before {
  content: "";
  flex: none;
  width: 0.5em;
  height: 0.5em;
  border-radius: var(--pulse-radius-pill);
  background: var(--tone);
}

.button {
  display: inline-flex;
  align-items: center;
  gap: var(--pulse-space-1);
  padding: var(--pulse-space-1) var(--pulse-space-3);
  border: var(--pulse-border-width-thin) solid var(--pulse-color-border-strong);
  border-radius: var(--pulse-radius-md);
  background: var(--pulse-color-surface-raised);
  color: var(--pulse-color-text-primary);
  font: inherit;
  font-size: var(--pulse-font-size-sm);
  cursor: pointer;
}

.button:hover {
  border-color: var(--pulse-color-accent-default);
}

/* Data tables: the view of every chart without JavaScript, and table visuals. */
.table-wrap {
  max-width: 100%;
  overflow-x: auto;
  border: var(--pulse-border-width-thin) solid var(--pulse-color-border-subtle);
  border-radius: var(--pulse-radius-md);
}

.table-wrap table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--pulse-font-size-sm);
}

.table-wrap th,
.table-wrap td {
  padding: var(--pulse-space-2) var(--pulse-space-3);
  border-block-end: var(--pulse-border-width-thin) solid var(--pulse-color-border-subtle);
  text-align: start;
  vertical-align: top;
}

.table-wrap thead th {
  background: var(--pulse-color-surface-sunken);
  color: var(--pulse-color-text-secondary);
  font-weight: var(--pulse-font-weight-semibold);
}

.table-wrap tbody tr:last-child > * {
  border-block-end: 0;
}

.table-wrap .num {
  text-align: end;
  font-variant-numeric: tabular-nums;
}

/* biome-ignore-start lint/complexity/noImportantStyles: reader preferences and print override components */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}

@media print {
  html,
  body {
    background: none;
  }

  [data-print="hide"] {
    display: none !important;
  }

  details::details-content {
    content-visibility: visible;
    display: contents;
  }

  a {
    color: inherit;
  }
}
/* biome-ignore-end lint/complexity/noImportantStyles: reader preferences and print override components */
```

`packages/site/src/client/theme.ts`:

```ts
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
```

`packages/site/src/client/theme-switch.ts`:

```ts
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
```

`packages/site/src/layouts/Base.astro`:

```astro
---
import "@pulse-generated/tokens/tokens.css";
import "@pulse-generated/tokens/fonts.css";
import "../styles/global.css";
import { MODES } from "@pulseai/tokens";
import SiteFooter from "../components/frame/SiteFooter.astro";
import SiteHeader from "../components/frame/SiteHeader.astro";
import { getSite } from "../lib/site-data.ts";
import { jsonForScript, THEME_DATA_ID, THEME_STORAGE_KEY } from "../lib/theme.ts";

interface Props {
  title: string;
  description?: string | undefined;
  /** Path below the base of the page this one duplicates (the front page repeats an edition). */
  canonical?: string | undefined;
}

const { title, description, canonical } = Astro.props;
const { ctx, theme, location } = getSite();
const { t } = ctx;
const themeChoices = ctx.enums.theme;
const defaultChoice = ctx.config.theme.default;
const modes = [...MODES];
const feed = location.site === undefined ? undefined : ctx.url("rss.xml");
---

<!doctype html>
<html lang={ctx.lang} data-theme-choice={defaultChoice}>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="color-scheme" content="light dark" />
    <title>{title}</title>
    <meta name="description" content={description ?? t("ui.site.description")} />
    <meta name="generator" content={Astro.generator} />
    {canonical !== undefined && <link rel="canonical" href={location.site === undefined ? ctx.url(canonical) : new URL(ctx.url(canonical), location.site).href} />}
    {feed && <link rel="alternate" type="application/rss+xml" title={t("ui.feed.title")} href={feed} />}
    <script is:inline define:vars={{ themeChoices, defaultChoice, modes, storageKey: THEME_STORAGE_KEY }}>
      // Runs before first paint so the page never flashes the wrong theme.
      let choice = defaultChoice;
      try {
        const stored = localStorage.getItem(storageKey);
        if (themeChoices.includes(stored)) choice = stored;
      } catch {
        // Storage is blocked; keep the configured default.
      }
      const query = new URLSearchParams(location.search).get("theme");
      if (themeChoices.includes(query)) choice = query;
      const root = document.documentElement;
      root.dataset.themeChoice = choice;
      if (modes.includes(choice)) root.dataset.theme = choice;
    </script>
    <script type="application/json" id={THEME_DATA_ID} set:html={jsonForScript(theme)}></script>
  </head>
  <body>
    <a class="skip-link" href="#main">{t("ui.nav.skip")}</a>
    <SiteHeader ctx={ctx} feed={feed} />
    <main id="main" class="page">
      <slot />
    </main>
    <SiteFooter ctx={ctx} />
  </body>
</html>
```

`packages/site/src/components/frame/SiteHeader.astro`:

```astro
---
import Search from "astro-pagefind/components/Search.astro";
import type { RenderContext } from "../../lib/render.ts";
import ThemeSwitch from "./ThemeSwitch.astro";

interface Props {
  ctx: RenderContext;
  feed: string | undefined;
}

const { ctx, feed } = Astro.props;
const { t, config } = ctx;
---

<header class="site-header" data-print="hide">
  <div class="page site-header__bar">
    <a class="site-header__brand" href={ctx.url("")}>{t("ui.site.title")}</a>
    <nav class="site-header__nav" aria-label={t("ui.nav.label")}>
      <a href={ctx.url("")}>{t("ui.nav.latest")}</a>
      <a href={ctx.url("archive/")}>{t("ui.nav.archive")}</a>
      {feed && <a href={feed}>{t("ui.nav.feed")}</a>}
    </nav>
    <div class="site-header__tools">
      {config.site.search && (
        <div class="site-header__search">
          <Search
            className="pulse-search"
            searchboxOptions={{ placeholder: t("ui.search.placeholder"), "aria-label": t("ui.search.label") }}
          />
        </div>
      )}
      {config.theme.switcher && <ThemeSwitch ctx={ctx} />}
    </div>
  </div>
</header>

<style>
  .site-header {
    border-block-end: var(--pulse-border-width-thin) solid var(--pulse-color-border-subtle);
    background: var(--pulse-color-surface-raised);
  }

  .site-header__bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--pulse-space-3) var(--pulse-space-5);
    padding-block: var(--pulse-space-3);
  }

  .site-header__brand {
    color: var(--pulse-color-text-primary);
    font-family: var(--pulse-font-family-display);
    font-size: var(--pulse-font-size-xl);
    font-weight: var(--pulse-font-weight-bold);
    text-decoration: none;
  }

  .site-header__nav {
    display: flex;
    gap: var(--pulse-space-4);
    font-size: var(--pulse-font-size-sm);
  }

  .site-header__nav a {
    color: var(--pulse-color-text-secondary);
    text-decoration: none;
  }

  .site-header__nav a:hover {
    color: var(--pulse-color-text-primary);
  }

  .site-header__tools {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--pulse-space-3);
    margin-inline-start: auto;
  }

  .site-header__search {
    min-width: min(18rem, 100%);
    --pf-text: var(--pulse-color-text-primary);
    --pf-text-secondary: var(--pulse-color-text-secondary);
    --pf-background: var(--pulse-color-surface-raised);
    --pf-border: var(--pulse-color-border-strong);
    --pf-border-focus: var(--pulse-color-focus-ring);
    --pf-hover: var(--pulse-color-surface-sunken);
    --pf-mark: color-mix(in oklab, var(--pulse-color-accent-default) 25%, transparent);
    --pf-font: var(--pulse-font-family-body);
  }
</style>
```

`packages/site/src/components/frame/ThemeSwitch.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";

interface Props {
  ctx: RenderContext;
}

const { ctx } = Astro.props;
const { t } = ctx;
---

<pulse-theme-switch hidden>
  <fieldset class="theme-switch">
    <legend class="visually-hidden">{t("ui.theme.label")}</legend>
    {ctx.enums.theme.map((choice) => (
      <label class="theme-switch__option">
        <input type="radio" name="pulse-theme" value={choice} />
        <span>{t(`ui.theme.${choice}`)}</span>
      </label>
    ))}
  </fieldset>
</pulse-theme-switch>

<script>
  import "../../client/theme-switch.ts";
</script>

<style>
  .theme-switch {
    display: inline-flex;
    margin: 0;
    padding: var(--pulse-space-1);
    border: var(--pulse-border-width-thin) solid var(--pulse-color-border-strong);
    border-radius: var(--pulse-radius-pill);
    background: var(--pulse-color-surface-sunken);
  }

  .theme-switch__option {
    position: relative;
  }

  .theme-switch__option input {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
  }

  .theme-switch__option span {
    display: block;
    padding: 0 var(--pulse-space-3);
    border-radius: var(--pulse-radius-pill);
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
    line-height: var(--pulse-font-line-height-relaxed);
  }

  .theme-switch__option input:checked + span {
    background: var(--pulse-color-surface-raised);
    color: var(--pulse-color-text-primary);
    font-weight: var(--pulse-font-weight-semibold);
  }

  .theme-switch__option input:focus-visible + span {
    outline: var(--pulse-border-width-thick) solid var(--pulse-color-focus-ring);
  }
</style>
```

`packages/site/src/components/frame/SiteFooter.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";

interface Props {
  ctx: RenderContext;
}

const { ctx } = Astro.props;
const { t } = ctx;
---

<footer class="site-footer">
  <div class="page site-footer__inner">
    <p>{t("ui.footer.generated", { version: ctx.engineVersion })}</p>
  </div>
</footer>

<style>
  .site-footer {
    margin-block-start: var(--pulse-space-8);
    border-block-start: var(--pulse-border-width-thin) solid var(--pulse-color-border-subtle);
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
  }

  .site-footer__inner {
    padding-block: var(--pulse-space-5);
  }
</style>
```

`packages/site/src/components/frame/Badge.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";

interface Props {
  ctx: RenderContext;
  /** Token path of the badge's tone (a semantic color), if it has one. */
  tone?: string | undefined;
  class?: string | undefined;
}

const { ctx, tone, class: className } = Astro.props;
---

<span
  class:list={["badge", className]}
  data-tone={tone === undefined ? undefined : tone}
  style={tone === undefined ? undefined : `--tone: ${ctx.cssVar(tone)}`}
><slot /></span>
```

`packages/site/src/components/frame/EmptyState.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";

interface Props {
  ctx: RenderContext;
}

const { ctx } = Astro.props;
const { t } = ctx;
---

<section class="empty">
  <h1>{t("ui.empty.title")}</h1>
  <p class="muted">{t("ui.empty.text")}</p>
</section>

<style>
  .empty {
    display: grid;
    gap: var(--pulse-space-3);
    padding-block: var(--pulse-space-8);
    text-align: center;
  }
</style>
```

`packages/site/src/pages/404.astro`:

```astro
---
import Base from "../layouts/Base.astro";
import { getSite } from "../lib/site-data.ts";

const { ctx } = getSite();
const { t } = ctx;
---

<Base title={`${t("ui.not_found.title")} · ${t("ui.site.title")}`}>
  <section class="not-found">
    <h1>{t("ui.not_found.title")}</h1>
    <p class="muted">{t("ui.not_found.text")}</p>
    <p><a href={ctx.url("")}>{t("ui.not_found.home")}</a></p>
  </section>
</Base>

<style>
  .not-found {
    display: grid;
    gap: var(--pulse-space-3);
    padding-block: var(--pulse-space-8);
    text-align: center;
  }
</style>
```

`packages/site/src/pages/index.astro` (temporary; Task 13 replaces it):

```astro
---
import EmptyState from "../components/frame/EmptyState.astro";
import Base from "../layouts/Base.astro";
import { allReports } from "../lib/reports.ts";
import { getSite } from "../lib/site-data.ts";

// A placeholder front page that lists the editions; Task 13 replaces it with the latest edition.
const { ctx } = getSite();
const reports = await allReports();
---

<Base title={ctx.t("ui.site.title")}>
  {reports.length === 0 ? (
    <EmptyState ctx={ctx} />
  ) : (
    <ol>
      {reports.map((report) => (
        <li><a href={ctx.url(`${report.meta.date.replaceAll("-", "/")}/`)}>{report.headline}</a></li>
      ))}
    </ol>
  )}
</Base>
```

- [ ] **Step 7: Add the demo scripts**

Add to the root `package.json` `scripts`:

```json
    "demo:context": "uv run pulse site context --instance examples",
    "demo:build": "pnpm demo:context && pnpm --filter @pulseai/site build:demo",
    "demo:dev": "pnpm demo:context && pnpm --filter @pulseai/site dev:demo",
    "demo:preview": "pnpm --filter @pulseai/site preview:demo",
    "demo:check": "pnpm --filter @pulseai/site check:demo",
```

- [ ] **Step 8: Run the tests and build the demo**

Run: `pnpm --filter @pulseai/site test && pnpm --filter @pulseai/site typecheck`
Expected: PASS. `foundation.test.ts` and `pulse-site.test.ts` pass, and `tsc` is clean even before any build has generated `.astro/` types.

Run: `pnpm demo:build && pnpm demo:check`
Expected:
- `[pulse-reports] loaded 3 reports`;
- `index.html` and `404.html` built in `examples/dist/`;
- `examples/.pulse/tokens/` holds `tokens.css`, `fonts.css`, `light.json` and `dark.json`;
- `astro check` reports 0 errors.

Run: `uv run pulse tokens check --instance examples`
Expected: `Design tokens pass.`

- [ ] **Step 9: Commit**

```bash
pnpm biome check --write . && pnpm lint
git add packages/site locales package.json pnpm-workspace.yaml pnpm-lock.yaml biome.json .gitignore .github/workflows/dependency-review.yml
git commit -m "feat(site): add the Astro site foundation

@pulseai/site loads an instance's reports through a validating content
loader, themes pages from the resolved tokens with an Auto/Light/Dark
switch, and builds with scripts/pulse-site.ts (tokens, then Astro). Every
string comes from the locales.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 8: Visuals — charts, diagrams, tables, figures, dashboards

**Files:**
- Create: `packages/site/src/lib/{visual-data,sparkline}.ts`
- Create: `packages/site/src/client/{vega-chart,mermaid-diagram}.ts`
- Create: `packages/site/src/components/visuals/{VisualFrame,DataTable,VegaLite,Mermaid,TableVisual,Figure,ImageRef,Sparkline,StatTile,VisualLeaf,Dashboard,Visual}.astro`
- Create: `packages/site/src/components/blocks/Code.astro`
- Create: `packages/site/test/visuals.test.ts`
- Modify: `.github/workflows/dependency-review.yml` (Mermaid's dependencies)

**Interfaces:**
- Consumes: `RenderContext`, `jsonForScript`, `themeData()`/`effectiveMode()`/`onModeChange()` (Task 7), report types.
- Produces:
  - `Visual` dispatches every visual kind: `Dashboard`, or `VisualLeaf` for `vega-lite`, `mermaid`, `table` and `image-ref`. `VegaLite` and `StatTile` are reused by later tasks.
  - `Figure` renders a hotlinked image with caption, credit and license. `Code` is a focusable `<pre>`.
  - `inlineTable(spec): DataTable | undefined` (`{ columns, rows }`) and `sparkline(series, width, height, padding)`.
- Client contract:
  - `<pulse-vega-chart>` holds its spec in a `<script type="application/json">` and draws into `[data-chart]`.
  - `<pulse-mermaid>` reads its code from the figure's `[data-diagram-source] code`.
  - Both set `data-state="rendered"` or `"error"` and re-render on every mode change.
  - The first successful chart render closes the figure's open `details[data-chart-table]`.
- Without JavaScript every chart shows its data table (open) and every diagram its alt text and source.

- [ ] **Step 1: Write the failing tests**

`packages/site/test/visuals.test.ts`:

```ts
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import Dashboard from "../src/components/visuals/Dashboard.astro";
import Mermaid from "../src/components/visuals/Mermaid.astro";
import VegaLite from "../src/components/visuals/VegaLite.astro";
import type { RenderContext } from "../src/lib/render.ts";
import { sparkline } from "../src/lib/sparkline.ts";
import type { Report } from "../src/lib/types.ts";
import { inlineTable } from "../src/lib/visual-data.ts";
import { sampleReport, testContext } from "./fixtures.ts";

let container: AstroContainer;
let ctx: RenderContext;
let report: Report;

beforeAll(async () => {
  container = await AstroContainer.create();
  ctx = await testContext("/PulseAI/");
  report = sampleReport();
});

describe("inline chart data", () => {
  it("reads top-level values, layers, and named datasets", () => {
    expect(
      inlineTable({
        data: {
          values: [
            { a: 1, b: 2 },
            { a: 3, c: 4 },
          ],
        },
      }),
    ).toEqual({
      columns: ["a", "b", "c"],
      rows: [
        [1, 2, null],
        [3, null, 4],
      ],
    });
    expect(
      inlineTable({ layer: [{ mark: "rule" }, { data: { values: [{ x: 1 }] } }] })?.rows,
    ).toEqual([[1]]);
    expect(inlineTable({ datasets: { d: [{ y: 2 }] } })?.columns).toEqual(["y"]);
  });

  it("has nothing to show for a spec without inline rows", () => {
    expect(inlineTable({ mark: "bar" })).toBeUndefined();
    expect(inlineTable({ data: { values: [] } })).toBeUndefined();
    expect(inlineTable("not a spec")).toBeUndefined();
  });
});

describe("sparkline", () => {
  it("needs two values and centres a flat series", () => {
    expect(sparkline([4], 100, 20, 2)).toBeUndefined();
    expect(sparkline([4, 4], 100, 20, 2)?.points).toBe("2,10 98,10");
  });

  it("spans the box and ends at the last value", () => {
    const line = sparkline([0, 10, 5], 100, 20, 0);
    expect(line?.points).toBe("0,20 50,0 100,10");
    expect(line?.last).toEqual({ x: 100, y: 10 });
  });
});

describe("visuals", () => {
  it("renders a chart over an open data table, with its spec escaped", async () => {
    const visual = {
      kind: "vega-lite" as const,
      id: "escape",
      title: "Escape",
      alt: "A chart",
      source_note: "Test",
      spec: { data: { values: [{ label: "</script>", value: 1 }] }, mark: "bar" },
    };
    const html = await container.renderToString(VegaLite, { props: { ctx, visual } });
    expect(html).toContain('<details class="visual__data" data-chart-table open');
    expect(html).toContain("\\u003c/script>");
    expect(html).toContain('role="img" aria-label="A chart"');
  });

  it("renders a diagram as alt text and source until it is drawn", async () => {
    const paper = report.items.find((candidate) => candidate.id === "verify-then-expand");
    const visual = paper?.visuals.find((candidate) => candidate.kind === "mermaid");
    const html = await container.renderToString(Mermaid, { props: { ctx, visual } });
    expect(html).toContain("data-diagram-fallback");
    expect(html).toContain("flowchart LR");
  });

  it("lays dashboard tiles on its columns", async () => {
    const [dashboard] = report.front_page;
    const html = await container.renderToString(Dashboard, { props: { ctx, visual: dashboard } });
    expect(html).toContain("--columns: 3");
    expect(html).toContain("--span: 2");
    expect(html).toContain('data-visual="table"');
  });
});
```

Run: `pnpm --filter @pulseai/site test -- visuals`
Expected: FAIL with `Cannot find module '../src/components/visuals/Dashboard.astro'`.

- [ ] **Step 2: Add the chart and diagram libraries**

Run: `pnpm --filter @pulseai/site add vega vega-lite vega-embed mermaid`

Mermaid brings `elkjs` (EPL-2.0, its layout engine) and `khroma` (MIT, but its `package.json` declares no license). In `.github/workflows/dependency-review.yml`, add both to `allow-dependencies-licenses`, with the reasons next to the existing ones:

```yaml
          #   khroma:            MIT     (license file; package.json declares none)
          # Packages outside the allow list, accepted on purpose:
          #   elkjs:             EPL-2.0 (Mermaid's layout engine, used unmodified as a library)
```

```yaml
            pkg:npm/khroma, pkg:npm/elkjs
```

- [ ] **Step 3: Write the data helpers**

`packages/site/src/lib/visual-data.ts`:

```ts
/** A chart's inline data as a table: the no-JavaScript and screen-reader view of every chart. */
export interface DataTable {
  columns: string[];
  rows: unknown[][];
}

type Node = { [key: string]: unknown };

function isNode(value: unknown): value is Node {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function rowsOf(spec: Node): Node[] | undefined {
  const data = spec.data;
  if (isNode(data) && Array.isArray(data.values)) return data.values.filter(isNode);
  if (Array.isArray(spec.layer)) {
    for (const layer of spec.layer) {
      if (isNode(layer)) {
        const found = rowsOf(layer);
        if (found !== undefined) return found;
      }
    }
  }
  if (isNode(spec.datasets)) {
    const first = Object.values(spec.datasets).find(Array.isArray);
    if (first !== undefined) return first.filter(isNode);
  }
  return undefined;
}

/** The first inline dataset of a Vega-Lite spec (top level, layers, then named datasets). */
export function inlineTable(spec: unknown): DataTable | undefined {
  if (!isNode(spec)) return undefined;
  const rows = rowsOf(spec);
  if (rows === undefined || rows.length === 0) return undefined;
  const columns: string[] = [];
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (!columns.includes(key)) columns.push(key);
    }
  }
  return { columns, rows: rows.map((row) => columns.map((column) => row[column] ?? null)) };
}
```

`packages/site/src/lib/sparkline.ts`:

```ts
export interface Sparkline {
  /** SVG polyline points, "x,y x,y …". */
  points: string;
  last: { x: number; y: number };
}

/**
 * Points for a small trend line in a width×height box with padding. A flat series sits in the
 * middle. Fewer than two values draw nothing.
 */
export function sparkline(
  series: readonly number[],
  width: number,
  height: number,
  padding: number,
): Sparkline | undefined {
  if (series.length < 2) return undefined;
  const min = Math.min(...series);
  const max = Math.max(...series);
  const span = max - min;
  const step = (width - 2 * padding) / (series.length - 1);
  const coords = series.map((value, index) => {
    const ratio = span === 0 ? 0.5 : (value - min) / span;
    const x = padding + index * step;
    const y = height - padding - ratio * (height - 2 * padding);
    return { x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100 };
  });
  const last = coords.at(-1);
  if (last === undefined) return undefined;
  return { points: coords.map(({ x, y }) => `${x},${y}`).join(" "), last };
}
```

- [ ] **Step 4: Write the client islands**

`packages/site/src/client/vega-chart.ts`:

```ts
import type { VisualizationSpec } from "vega-embed";
import { effectiveMode, onModeChange, themeData } from "./theme.ts";

type Spec = { [key: string]: unknown };

/** A Vega-Lite chart that renders over its data table and re-themes with the page. */
class PulseVegaChart extends HTMLElement {
  #spec: Spec | undefined;
  #view: { finalize(): void } | undefined;
  #rendered = false;

  connectedCallback(): void {
    const source = this.querySelector<HTMLScriptElement>("script[type='application/json']");
    try {
      this.#spec = JSON.parse(source?.textContent ?? "") as Spec;
    } catch (error) {
      this.#fail(error);
      return;
    }
    onModeChange(() => void this.render());
    void this.render();
  }

  disconnectedCallback(): void {
    this.#view?.finalize();
  }

  async render(): Promise<void> {
    const canvas = this.querySelector<HTMLElement>("[data-chart]");
    if (canvas === null || this.#spec === undefined) return;
    try {
      const { default: embed } = await import("vega-embed");
      // Charts fill their figure unless the spec sets a width.
      const spec = { width: "container", ...this.#spec } as unknown as VisualizationSpec;
      const result = await embed(canvas, spec, {
        actions: false,
        renderer: "svg",
        config: themeData().vega[effectiveMode()],
        tooltip: { theme: "custom" },
      });
      this.#view?.finalize();
      this.#view = result;
      canvas.hidden = false;
      if (!this.#rendered) {
        // The table stays one click away for readers who want the numbers.
        this.closest("figure")?.querySelector("details[data-chart-table]")?.removeAttribute("open");
        this.#rendered = true;
      }
      this.dataset.state = "rendered";
    } catch (error) {
      this.#fail(error);
    }
  }

  #fail(error: unknown): void {
    this.dataset.state = "error";
    console.error(`chart ${this.closest("figure")?.id ?? ""} failed to render`, error);
  }
}

if (!customElements.get("pulse-vega-chart")) {
  customElements.define("pulse-vega-chart", PulseVegaChart);
}
```

`packages/site/src/client/mermaid-diagram.ts`:

```ts
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
      const { default: mermaid } = await import("mermaid");
      const variables = themeData().mermaid[effectiveMode()];
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: "base",
        themeVariables: variables,
        fontFamily: variables.fontFamily,
      });
      sequence += 1;
      const { svg } = await mermaid.render(`pulse-mermaid-${sequence}`, code);
      // Mermaid sanitizes its output under securityLevel "strict".
      canvas.innerHTML = svg;
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
```

- [ ] **Step 5: Write the visual components**

`packages/site/src/components/visuals/VisualFrame.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";

interface Props {
  ctx: RenderContext;
  id: string;
  kind: string;
  title: string;
  sourceNote: string;
  /** Inside a dashboard tile the title is smaller and the source note is the dashboard's. */
  nested?: boolean;
}

const { ctx, id, kind, title, sourceNote, nested = false } = Astro.props;
---

<figure class:list={["visual", { "visual--nested": nested }]} id={`visual-${id}`} data-visual={kind}>
  <figcaption class="visual__title">{title}</figcaption>
  <slot />
  {!nested && <p class="visual__source">{ctx.t("ui.visual.source", { source: sourceNote })}</p>}
</figure>

<style>
  .visual {
    display: grid;
    gap: var(--pulse-space-2);
    min-width: 0;
    padding: var(--pulse-space-4);
    border: var(--pulse-border-width-thin) solid var(--pulse-color-border-subtle);
    border-radius: var(--pulse-radius-lg);
    background: var(--pulse-color-surface-raised);
  }

  .visual--nested {
    height: 100%;
    padding: var(--pulse-space-3);
    border-radius: var(--pulse-radius-md);
  }

  .visual__title {
    font-family: var(--pulse-font-family-body);
    font-size: var(--pulse-font-size-md);
    font-weight: var(--pulse-font-weight-semibold);
  }

  .visual--nested .visual__title {
    font-size: var(--pulse-font-size-sm);
  }

  .visual__source {
    color: var(--pulse-color-text-muted);
    font-size: var(--pulse-font-size-xs);
  }

  .visual :global(.visual__data summary) {
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
    cursor: pointer;
  }

  .visual :global(.visual__data[open] summary) {
    margin-block-end: var(--pulse-space-2);
  }

  .visual :global(.visual__alt) {
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
  }
</style>
```

`packages/site/src/components/visuals/DataTable.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";

interface Props {
  ctx: RenderContext;
  columns: readonly string[];
  rows: readonly (readonly unknown[])[];
  caption: string;
  /** Hide the caption when a visible title already names the table. */
  hideCaption?: boolean;
}

const { ctx, columns, rows, caption, hideCaption = false } = Astro.props;
---

<div class="table-wrap" role="region" aria-label={caption} tabindex="0">
  <table>
    <caption class:list={[{ "visually-hidden": hideCaption }]}>{caption}</caption>
    <thead>
      <tr>{columns.map((column) => <th scope="col">{column}</th>)}</tr>
    </thead>
    <tbody>
      {rows.map((row) => (
        <tr>
          {row.map((cell) => (
            <td class:list={[{ num: typeof cell === "number" }]}>{ctx.fmt.value(cell, ctx.t)}</td>
          ))}
        </tr>
      ))}
    </tbody>
  </table>
</div>

<style>
  caption {
    padding-block: var(--pulse-space-2);
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
    text-align: start;
    caption-side: top;
  }
</style>
```

`packages/site/src/components/visuals/VegaLite.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import { jsonForScript } from "../../lib/theme.ts";
import type { VegaLiteVisual } from "../../lib/types.ts";
import { inlineTable } from "../../lib/visual-data.ts";
import DataTable from "./DataTable.astro";
import VisualFrame from "./VisualFrame.astro";

interface Props {
  ctx: RenderContext;
  visual: VegaLiteVisual;
  nested?: boolean;
}

const { ctx, visual, nested = false } = Astro.props;
const { t } = ctx;
const table = inlineTable(visual.spec);
---

<VisualFrame ctx={ctx} id={visual.id} kind={visual.kind} title={visual.title} sourceNote={visual.source_note} nested={nested}>
  <pulse-vega-chart class="chart" role="img" aria-label={visual.alt}>
    <script type="application/json" set:html={jsonForScript(visual.spec)}></script>
    <div class="chart__canvas" data-chart hidden></div>
  </pulse-vega-chart>
  {table ? (
    <details class="visual__data" data-chart-table open>
      <summary>{t("ui.visual.data")}</summary>
      <DataTable ctx={ctx} columns={table.columns} rows={table.rows} caption={visual.title} hideCaption />
    </details>
  ) : (
    <p class="visual__alt">{visual.alt}</p>
  )}
</VisualFrame>

<script>
  import "../../client/vega-chart.ts";
</script>

<style>
  .chart {
    display: block;
    min-width: 0;
  }

  .chart__canvas {
    width: 100%;
  }

  .chart__canvas :global(.vega-embed) {
    width: 100%;
  }

  .chart[data-state="error"] .chart__canvas {
    display: none;
  }
</style>
```

`packages/site/src/components/blocks/Code.astro`:

```astro
---
interface Props {
  code: string;
}

// Code scrolls sideways on narrow screens, so keyboard users must be able to focus it.
const { code } = Astro.props;
---

<pre tabindex="0"><code>{code}</code></pre>
```

`packages/site/src/components/visuals/Mermaid.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { MermaidVisual } from "../../lib/types.ts";
import Code from "../blocks/Code.astro";
import VisualFrame from "./VisualFrame.astro";

interface Props {
  ctx: RenderContext;
  visual: MermaidVisual;
  nested?: boolean;
}

const { ctx, visual, nested = false } = Astro.props;
const { t } = ctx;
---

<VisualFrame ctx={ctx} id={visual.id} kind={visual.kind} title={visual.title} sourceNote={visual.source_note} nested={nested}>
  <pulse-mermaid class="diagram" role="img" aria-label={visual.alt}>
    <div class="diagram__canvas" data-diagram hidden></div>
    <p class="visual__alt" data-diagram-fallback>{visual.alt}</p>
  </pulse-mermaid>
  <details class="visual__data" data-diagram-source>
    <summary>{t("ui.visual.diagram_source")}</summary>
    <Code code={visual.code} />
  </details>
</VisualFrame>

<script>
  import "../../client/mermaid-diagram.ts";
</script>

<style>
  .diagram {
    display: block;
    min-width: 0;
  }

  .diagram__canvas {
    overflow-x: auto;
    text-align: center;
  }

  .diagram__canvas :global(svg) {
    height: auto;
  }
</style>
```

`packages/site/src/components/visuals/TableVisual.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { TableVisual } from "../../lib/types.ts";
import DataTable from "./DataTable.astro";
import VisualFrame from "./VisualFrame.astro";

interface Props {
  ctx: RenderContext;
  visual: TableVisual;
  nested?: boolean;
}

const { ctx, visual, nested = false } = Astro.props;
---

<VisualFrame ctx={ctx} id={visual.id} kind={visual.kind} title={visual.title} sourceNote={visual.source_note} nested={nested}>
  <DataTable ctx={ctx} columns={visual.columns} rows={visual.rows} caption={visual.alt} hideCaption />
</VisualFrame>
```

`packages/site/src/components/visuals/Figure.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { ItemImage } from "../../lib/types.ts";

interface Props {
  ctx: RenderContext;
  image: ItemImage;
}

// Real images are hotlinked, never copied: the source's license may not allow copies.
const { ctx, image } = Astro.props;
const { t } = ctx;
---

<figure class="figure">
  <img src={image.url} alt={image.alt} loading="lazy" decoding="async" referrerpolicy="no-referrer" />
  <figcaption>
    {image.caption}
    <span class="figure__credit">
      {t("ui.image.credit", { credit: image.credit })}{image.license && ` · ${t("ui.image.license", { license: image.license })}`}
    </span>
  </figcaption>
</figure>

<style>
  .figure {
    display: grid;
    gap: var(--pulse-space-2);
  }

  .figure img {
    display: block;
    width: 100%;
    max-height: 28rem;
    object-fit: contain;
    border: var(--pulse-border-width-thin) solid var(--pulse-color-border-subtle);
    border-radius: var(--pulse-radius-md);
    background: var(--pulse-color-surface-sunken);
  }

  figcaption {
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
  }

  .figure__credit {
    display: block;
    color: var(--pulse-color-text-muted);
    font-size: var(--pulse-font-size-xs);
  }
</style>
```

`packages/site/src/components/visuals/ImageRef.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { ImageRefVisual } from "../../lib/types.ts";
import Figure from "./Figure.astro";
import VisualFrame from "./VisualFrame.astro";

interface Props {
  ctx: RenderContext;
  visual: ImageRefVisual;
  nested?: boolean;
}

const { ctx, visual, nested = false } = Astro.props;
---

<VisualFrame ctx={ctx} id={visual.id} kind={visual.kind} title={visual.title} sourceNote={visual.source_note} nested={nested}>
  <Figure ctx={ctx} image={visual.image} />
</VisualFrame>
```

`packages/site/src/components/visuals/Sparkline.astro`:

```astro
---
import { sparkline } from "../../lib/sparkline.ts";

interface Props {
  series: readonly number[];
}

// A decorative trend: the value and delta next to it carry the meaning for every reader.
const WIDTH = 96;
const HEIGHT = 28;
const PADDING = 3;
const { series } = Astro.props;
const line = sparkline(series, WIDTH, HEIGHT, PADDING);
---

{line && (
  <svg class="sparkline" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width={WIDTH} height={HEIGHT} aria-hidden="true" focusable="false">
    <polyline points={line.points} />
    <circle cx={line.last.x} cy={line.last.y} r="2.5" />
  </svg>
)}

<style>
  .sparkline {
    display: block;
    overflow: visible;
  }

  polyline {
    fill: none;
    stroke: var(--pulse-color-accent-default);
    stroke-width: var(--pulse-chart-line-width);
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  circle {
    fill: var(--pulse-color-accent-default);
  }
</style>
```

`packages/site/src/components/visuals/StatTile.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import Sparkline from "./Sparkline.astro";

interface Props {
  ctx: RenderContext;
  label: string;
  value: string | number;
  unit?: string | undefined;
  delta?: number | undefined;
  series?: readonly number[] | undefined;
}

const { ctx, label, value, unit, delta, series } = Astro.props;
const { t, fmt } = ctx;
const shown = typeof value === "number" ? fmt.number(value) : value;
const direction = delta === undefined ? undefined : delta > 0 ? "up" : delta < 0 ? "down" : "flat";
---

<div class="stat">
  <p class="stat__label">{label}</p>
  <p class="stat__value">
    {shown}{unit && <span class="stat__unit">{unit}</span>}
  </p>
  <div class="stat__trend">
    {delta !== undefined && direction !== undefined && (
      <p class="stat__delta" data-direction={direction}>
        <span aria-hidden="true">{fmt.signed(delta)}</span>
        <span class="visually-hidden">{t(`ui.delta.${direction}`, { value: fmt.number(Math.abs(delta)) })}</span>
      </p>
    )}
    {series && <Sparkline series={series} />}
  </div>
</div>

<style>
  .stat {
    display: grid;
    gap: var(--pulse-space-1);
    height: 100%;
  }

  .stat__label {
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
  }

  .stat__value {
    font-family: var(--pulse-font-family-display);
    font-size: var(--pulse-font-size-3xl);
    font-weight: var(--pulse-font-weight-semibold);
    line-height: var(--pulse-font-line-height-tight);
    overflow-wrap: anywhere;
  }

  .stat__unit {
    margin-inline-start: var(--pulse-space-1);
    color: var(--pulse-color-text-secondary);
    font-family: var(--pulse-font-family-body);
    font-size: var(--pulse-font-size-sm);
    font-weight: var(--pulse-font-weight-regular);
  }

  .stat__trend {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--pulse-space-3);
    min-height: var(--pulse-space-5);
  }

  .stat__delta {
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
    font-variant-numeric: tabular-nums;
  }
</style>
```

`packages/site/src/components/visuals/VisualLeaf.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { LeafVisual } from "../../lib/types.ts";
import ImageRef from "./ImageRef.astro";
import Mermaid from "./Mermaid.astro";
import TableVisual from "./TableVisual.astro";
import VegaLite from "./VegaLite.astro";

interface Props {
  ctx: RenderContext;
  visual: LeafVisual;
  nested?: boolean;
}

const { ctx, visual, nested = false } = Astro.props;
---

{visual.kind === "vega-lite" && <VegaLite ctx={ctx} visual={visual} nested={nested} />}
{visual.kind === "mermaid" && <Mermaid ctx={ctx} visual={visual} nested={nested} />}
{visual.kind === "table" && <TableVisual ctx={ctx} visual={visual} nested={nested} />}
{visual.kind === "image-ref" && <ImageRef ctx={ctx} visual={visual} nested={nested} />}
```

`packages/site/src/components/visuals/Dashboard.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { DashboardVisual } from "../../lib/types.ts";
import StatTile from "./StatTile.astro";
import VisualFrame from "./VisualFrame.astro";
import VisualLeaf from "./VisualLeaf.astro";

interface Props {
  ctx: RenderContext;
  visual: DashboardVisual;
}

const { ctx, visual } = Astro.props;
---

<VisualFrame ctx={ctx} id={visual.id} kind={visual.kind} title={visual.title} sourceNote={visual.source_note}>
  <div class="dashboard" role="group" aria-label={visual.alt} style={`--columns: ${visual.columns}`}>
    {visual.tiles.map((tile) => (
      <div class:list={["dashboard__tile", `dashboard__tile--${tile.tile}`]} style={`--span: ${tile.span ?? 1}`}>
        {tile.tile === "stat" ? (
          <StatTile ctx={ctx} label={tile.label} value={tile.value} unit={tile.unit} delta={tile.delta} series={tile.series} />
        ) : (
          <VisualLeaf ctx={ctx} visual={tile.visual} nested />
        )}
      </div>
    ))}
  </div>
</VisualFrame>

<style>
  .dashboard {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--pulse-space-3);
  }

  .dashboard__tile {
    min-width: 0;
  }

  .dashboard__tile--stat {
    padding: var(--pulse-space-3);
    border: var(--pulse-border-width-thin) solid var(--pulse-color-border-subtle);
    border-radius: var(--pulse-radius-md);
    background: var(--pulse-color-surface-page);
  }

  @media (min-width: 40rem) {
    .dashboard {
      grid-template-columns: repeat(min(var(--columns), 2), minmax(0, 1fr));
    }

    .dashboard__tile {
      grid-column: span min(var(--span), 2);
    }
  }

  @media (min-width: 64rem) {
    .dashboard {
      grid-template-columns: repeat(var(--columns), minmax(0, 1fr));
    }

    .dashboard__tile {
      grid-column: span var(--span);
    }
  }
</style>
```

`packages/site/src/components/visuals/Visual.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { Visual } from "../../lib/types.ts";
import Dashboard from "./Dashboard.astro";
import VisualLeaf from "./VisualLeaf.astro";

interface Props {
  ctx: RenderContext;
  visual: Visual;
}

const { ctx, visual } = Astro.props;
---

{visual.kind === "dashboard" ? <Dashboard ctx={ctx} visual={visual} /> : <VisualLeaf ctx={ctx} visual={visual} />}
```

- [ ] **Step 6: Run the tests**

Run: `pnpm --filter @pulseai/site test && pnpm --filter @pulseai/site typecheck && pnpm demo:check`
Expected: all site tests pass, and `tsc` and `astro check` report 0 errors.

- [ ] **Step 7: Commit**

```bash
pnpm biome check --write packages/site .github && pnpm lint
git add packages/site .github/workflows/dependency-review.yml pnpm-lock.yaml
git commit -m "feat(site): render charts, diagrams, tables, figures, and dashboards

Vega-Lite charts and Mermaid diagrams are custom elements themed from the
resolved tokens; without JavaScript, charts show their data table and
diagrams their alt text and source. Dashboards lay stat tiles and visuals
on a grid.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 9: The top of a report — masthead, numbers, TL;DR, front page, radar, actions

**Files:**
- Create: `packages/site/src/components/frame/{Masthead,PulseScore,KpiTiles,Tldr,FrontPage,AdoptionRadar,ActionList}.astro`
- Create: `packages/site/test/frame-top.test.ts`

**Interfaces:**
- Consumes: `RenderContext` and `Badge` (Task 7); `StatTile` and `Visual` (Task 8).
- Produces: `<Masthead ctx report>`, `<KpiTiles ctx kpis>`, `<Tldr ctx lines>`, `<FrontPage ctx visuals>`, `<AdoptionRadar ctx entries items>`, `<ActionList ctx actions>`. Each renders nothing when its data is empty. Rings follow the schema enum order.
- Rules:
  - Only an unusual edition is badged: the schema lists the regular edition (`normal`) first.
  - The score gauge spans 1.25× the larger of today's value and the 7-day average.

- [ ] **Step 1: Write the failing tests**

`packages/site/test/frame-top.test.ts`:

```ts
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import ActionList from "../src/components/frame/ActionList.astro";
import AdoptionRadar from "../src/components/frame/AdoptionRadar.astro";
import FrontPage from "../src/components/frame/FrontPage.astro";
import KpiTiles from "../src/components/frame/KpiTiles.astro";
import Masthead from "../src/components/frame/Masthead.astro";
import Tldr from "../src/components/frame/Tldr.astro";
import type { RenderContext } from "../src/lib/render.ts";
import type { Report } from "../src/lib/types.ts";
import { sampleReport, testContext } from "./fixtures.ts";

let container: AstroContainer;
let ctx: RenderContext;
let report: Report;

beforeAll(async () => {
  container = await AstroContainer.create();
  ctx = await testContext("/PulseAI/");
  report = sampleReport();
});

describe("report top", () => {
  it("renders nothing for empty regions", async () => {
    const empty = [
      [KpiTiles, { ctx, kpis: [] }],
      [Tldr, { ctx, lines: [] }],
      [AdoptionRadar, { ctx, entries: [], items: [] }],
      [FrontPage, { ctx, visuals: [] }],
      [ActionList, { ctx, actions: [] }],
    ] as const;
    for (const [component, props] of empty) {
      expect((await container.renderToString(component, { props })).trim()).toBe("");
    }
  });

  it("orders radar rings as the schema does", async () => {
    const html = await container.renderToString(AdoptionRadar, {
      props: { ctx, entries: report.adoption_radar, items: report.items },
    });
    const order = ["Adopt", "Trial", "Assess", "Hold"].map((label) => html.indexOf(label));
    expect(order).toEqual([...order].sort((a, b) => a - b));
  });

  it("marks a sample edition and compares the score with the 7-day average", async () => {
    const html = await container.renderToString(Masthead, { props: { ctx, report } });
    expect(html).toContain("Sample edition");
    expect(html).toContain("+33.5 against the 7-day average of 11.5");
    const first = sampleReport("2026-10-09");
    expect(await container.renderToString(Masthead, { props: { ctx, report: first } })).toContain(
      "No 7-day average yet",
    );
  });
});
```

Run: `pnpm --filter @pulseai/site test -- frame-top`
Expected: FAIL with `Cannot find module '../src/components/frame/ActionList.astro'`.

- [ ] **Step 2: Write the components**

`packages/site/src/components/frame/PulseScore.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { Report } from "../../lib/types.ts";

interface Props {
  ctx: RenderContext;
  score: Report["pulse_score"];
}

const { ctx, score } = Astro.props;
const { t, fmt } = ctx;
const average = score.avg_7d;
// The gauge spans a quarter more than the larger of today and the average.
const scale = Math.max(score.value, average ?? 0, 1) * 1.25;
const width = (value: number) => `${Math.round((value / scale) * 1000) / 10}%`;
const comparison =
  average === null
    ? t("ui.score.no_avg")
    : t("ui.score.vs_avg", {
        delta: fmt.signed(Math.round((score.value - average) * 10) / 10),
        average: fmt.number(average),
      });
---

<div class="score">
  <p class="score__label">{t("ui.score.label")}</p>
  <p class="score__value">{fmt.number(score.value)}</p>
  <div class="score__gauge" aria-hidden="true">
    <span class="score__bar" style={`inline-size: ${width(score.value)}`}></span>
    {average !== null && <span class="score__marker" style={`inset-inline-start: ${width(average)}`}></span>}
  </div>
  <p class="score__comparison">{comparison}</p>
</div>

<style>
  .score {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: var(--pulse-space-1) var(--pulse-space-4);
    max-width: var(--pulse-layout-reading-width);
  }

  .score__label {
    grid-column: 1 / -1;
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
  }

  .score__value {
    font-family: var(--pulse-font-family-display);
    font-size: var(--pulse-font-size-3xl);
    font-weight: var(--pulse-font-weight-bold);
    line-height: var(--pulse-font-line-height-tight);
    font-variant-numeric: tabular-nums;
  }

  .score__gauge {
    position: relative;
    block-size: var(--pulse-space-3);
    border-radius: var(--pulse-radius-pill);
    background: var(--pulse-color-surface-sunken);
  }

  .score__bar {
    position: absolute;
    inset-block: 0;
    inset-inline-start: 0;
    border-radius: var(--pulse-radius-pill);
    background: var(--pulse-color-accent-default);
  }

  .score__marker {
    position: absolute;
    inset-block: calc(-1 * var(--pulse-space-1));
    inline-size: var(--pulse-border-width-thick);
    background: var(--pulse-color-text-primary);
  }

  .score__comparison {
    grid-column: 1 / -1;
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
  }
</style>
```

`packages/site/src/components/frame/Masthead.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { Report } from "../../lib/types.ts";
import Badge from "./Badge.astro";
import PulseScore from "./PulseScore.astro";

interface Props {
  ctx: RenderContext;
  report: Report;
}

const { ctx, report } = Astro.props;
const { t, fmt } = ctx;
const { meta } = report;
const window = {
  start: fmt.dateTime(meta.window.start, meta.window.tz),
  end: fmt.dateTime(meta.window.end, meta.window.tz),
  tz: meta.window.tz,
};
// Only an unusual edition says what kind it is; the schema lists the regular edition first.
const regular = ctx.enums.edition[0];
---

<header class="masthead">
  <div class="masthead__meta">
    <p class="masthead__edition">
      {t("ui.masthead.edition", { edition: meta.edition })} · <time datetime={meta.date}>{fmt.date(meta.date)}</time>
    </p>
    <div class="masthead__badges">
      {meta.sample && <Badge ctx={ctx} tone="color.status.warning">{t("ui.masthead.sample")}</Badge>}
      {meta.mode !== regular && <Badge ctx={ctx} tone="color.status.serious">{t(`modes.${meta.mode}`)}</Badge>}
    </div>
  </div>
  <h1 class="masthead__headline">{report.headline}</h1>
  <p class="masthead__window">{t("ui.masthead.window", window)}</p>
  <PulseScore ctx={ctx} score={report.pulse_score} />
</header>

<style>
  .masthead {
    display: grid;
    gap: var(--pulse-space-3);
    padding-block: var(--pulse-space-7) var(--pulse-space-5);
    border-block-end: var(--pulse-border-width-thick) solid var(--pulse-color-text-primary);
  }

  .masthead__meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--pulse-space-2);
  }

  .masthead__edition {
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
    font-weight: var(--pulse-font-weight-medium);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .masthead__badges {
    display: flex;
    gap: var(--pulse-space-2);
  }

  .masthead__headline {
    max-width: 22ch;
    font-size: clamp(var(--pulse-font-size-2xl), 6vw, var(--pulse-font-size-3xl));
  }

  .masthead__window {
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
  }
</style>
```

`packages/site/src/components/frame/KpiTiles.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { Kpi } from "../../lib/types.ts";
import StatTile from "../visuals/StatTile.astro";

interface Props {
  ctx: RenderContext;
  kpis: readonly Kpi[];
}

const { ctx, kpis } = Astro.props;
---

{kpis.length > 0 && (
  <section class="kpis" aria-labelledby="kpis-title">
    <h2 class="visually-hidden" id="kpis-title">{ctx.t("ui.kpis.title")}</h2>
    <ul class="kpis__list">
      {kpis.map((kpi) => (
        <li class="kpis__tile">
          <StatTile ctx={ctx} label={kpi.label} value={kpi.value} delta={kpi.delta} series={kpi.series} />
        </li>
      ))}
    </ul>
  </section>
)}

<style>
  .kpis {
    margin-block: var(--pulse-space-5);
  }

  .kpis__list {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(12rem, 100%), 1fr));
    gap: var(--pulse-space-3);
    padding: 0;
    list-style: none;
  }

  .kpis__tile {
    padding: var(--pulse-space-4);
    border: var(--pulse-border-width-thin) solid var(--pulse-color-border-subtle);
    border-radius: var(--pulse-radius-lg);
    background: var(--pulse-color-surface-raised);
  }
</style>
```

`packages/site/src/components/frame/Tldr.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { Report } from "../../lib/types.ts";

interface Props {
  ctx: RenderContext;
  lines: Report["tldr"];
}

const { ctx, lines } = Astro.props;
---

{lines.length > 0 && (
  <section class="region tldr" aria-labelledby="tldr-title">
    <h2 class="region__title" id="tldr-title">{ctx.t("ui.tldr.title")}</h2>
    <ol class="tldr__list">
      {lines.map((line) => (
        <li><a href={`#${line.item_id}`}>{line.text}</a></li>
      ))}
    </ol>
  </section>
)}

<style>
  .tldr__list {
    display: grid;
    gap: var(--pulse-space-2);
    max-width: var(--pulse-layout-reading-width);
    padding-inline-start: var(--pulse-space-5);
    font-size: var(--pulse-font-size-lg);
  }

  .tldr__list a {
    color: var(--pulse-color-text-primary);
    text-decoration-color: var(--pulse-color-border-strong);
  }

  .tldr__list a:hover {
    text-decoration-color: var(--pulse-color-accent-default);
  }

  .tldr__list li::marker {
    color: var(--pulse-color-text-muted);
    font-variant-numeric: tabular-nums;
  }
</style>
```

`packages/site/src/components/frame/FrontPage.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { Visual as VisualData } from "../../lib/types.ts";
import Visual from "../visuals/Visual.astro";

interface Props {
  ctx: RenderContext;
  visuals: readonly VisualData[];
}

const { ctx, visuals } = Astro.props;
---

{visuals.length > 0 && (
  <section class="region front-page" aria-labelledby="front-page-title">
    <h2 class="visually-hidden" id="front-page-title">{ctx.t("ui.front_page.title")}</h2>
    <div class="front-page__grid">
      {visuals.map((visual) => <Visual ctx={ctx} visual={visual} />)}
    </div>
  </section>
)}

<style>
  .front-page__grid {
    display: grid;
    gap: var(--pulse-space-4);
  }
</style>
```

`packages/site/src/components/frame/AdoptionRadar.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { Item, RadarEntry } from "../../lib/types.ts";
import Badge from "./Badge.astro";

interface Props {
  ctx: RenderContext;
  entries: readonly RadarEntry[];
  items: readonly Item[];
}

const { ctx, entries, items } = Astro.props;
const { t } = ctx;
const titles = new Map(items.map((item) => [item.id, item.title]));
// Rings in schema order (adopt first); empty rings are left out.
const rings = ctx.enums.ring
  .map((ring) => ({ ring, entries: entries.filter((entry) => entry.ring === ring) }))
  .filter((group) => group.entries.length > 0);
---

{rings.length > 0 && (
  <section class="region radar" aria-labelledby="radar-title">
    <h2 class="region__title" id="radar-title">{t("ui.radar.title")}</h2>
    <div class="radar__rings">
      {rings.map(({ ring, entries: ringEntries }) => (
        <section class="radar__ring" aria-labelledby={`radar-${ring}`}>
          <h3 class="radar__ring-title" id={`radar-${ring}`}>
            <Badge ctx={ctx} tone={`color.ring.${ring}`}>{t(`rings.${ring}`)}</Badge>
          </h3>
          <ul class="radar__entries">
            {ringEntries.map((entry) => (
              <li>
                <a href={`#${entry.item_id}`}>{titles.get(entry.item_id) ?? entry.item_id}</a>
                <p class="muted">{entry.rationale}</p>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  </section>
)}

<style>
  .radar__rings {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(14rem, 100%), 1fr));
    gap: var(--pulse-space-3);
  }

  .radar__ring {
    padding: var(--pulse-space-4);
    border: var(--pulse-border-width-thin) solid var(--pulse-color-border-subtle);
    border-radius: var(--pulse-radius-lg);
    background: var(--pulse-color-surface-raised);
  }

  .radar__ring-title {
    margin-block-end: var(--pulse-space-3);
    font-size: var(--pulse-font-size-md);
  }

  .radar__entries {
    display: grid;
    gap: var(--pulse-space-3);
    padding: 0;
    list-style: none;
    font-size: var(--pulse-font-size-sm);
  }

  .radar__entries a {
    font-weight: var(--pulse-font-weight-semibold);
  }
</style>
```

`packages/site/src/components/frame/ActionList.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { Report } from "../../lib/types.ts";

interface Props {
  ctx: RenderContext;
  actions: Report["action_list"];
}

const { ctx, actions } = Astro.props;
---

{actions.length > 0 && (
  <section class="region actions" aria-labelledby="actions-title">
    <h2 class="region__title" id="actions-title">{ctx.t("ui.actions.title")}</h2>
    <ol class="actions__list">
      {actions.map((action) => (
        <li>{action.item_id ? <a href={`#${action.item_id}`}>{action.text}</a> : action.text}</li>
      ))}
    </ol>
  </section>
)}

<style>
  .actions__list {
    display: grid;
    gap: var(--pulse-space-2);
    max-width: var(--pulse-layout-reading-width);
    padding: var(--pulse-space-4) var(--pulse-space-4) var(--pulse-space-4) var(--pulse-space-7);
    border-inline-start: var(--pulse-border-width-thick) solid var(--pulse-color-accent-default);
    background: var(--pulse-color-surface-raised);
    border-radius: var(--pulse-radius-md);
  }
</style>
```

- [ ] **Step 3: Run the tests**

Run: `pnpm --filter @pulseai/site test && pnpm --filter @pulseai/site typecheck && pnpm demo:check`
Expected: PASS with 0 errors.

- [ ] **Step 4: Commit**

```bash
pnpm biome check --write packages/site && pnpm lint
git add packages/site
git commit -m "feat(site): render the top of a report

Masthead with the Pulse score against the 7-day average, key numbers with
sparklines, TL;DR, front-page visuals, the adoption radar in schema ring
order, and the action list. Empty regions render nothing.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 10: Items — the expandable shell, briefs, facts, sources, and blocks

**Files:**
- Create: `packages/site/src/lib/report.ts`
- Create: `packages/site/src/components/blocks/{Block,KeyValues}.astro`
- Create: `packages/site/src/components/items/{Scores,Facts,Sources,BriefFields,ItemShell,ItemDetail,GenericDetail}.astro`
- Create: `packages/site/test/items.test.ts`

**Interfaces:**
- Consumes: `RenderContext`, `Badge` (Task 7); `Visual`, `Figure` (Task 8).
- Produces:
  - Report helpers in `lib/report.ts`:
    - `itemDepth(item, minImpact): "deep" | "brief"`
    - `matchesGroup(item, group, featured, minImpact)`
    - `groupItems(section, items, featured, minImpact): ItemGroup[]`. Each item goes to the first group it matches; the leftovers come last, with `group: undefined`; empty groups are dropped.
    - `sectionItems(report, id)`, `blockVisuals(item, block)`, `looseVisuals(item, blocks)`, `reportPath(date)`, `leafVisuals(visual)`
  - `<ItemShell ctx item>` renders `<details data-item id={item.id}>` with `data-section`, `data-type`, `data-impact`, `data-confidence`, `data-update` and `data-depth`.
  - `<Block ctx item id>` renders its slot plus the visuals placed in that block, or nothing if both are empty.
  - `<ItemDetail ctx item itemType>` picks `components/items/types/<registry component>.astro`, falling back to `GenericDetail`.
  - `<KeyValues entries>` skips empty values.
- A type component file (Task 11) is only discovered by `ItemDetail`; until it exists, every type renders through `GenericDetail`.

- [ ] **Step 1: Write the failing tests**

`packages/site/test/items.test.ts`:

```ts
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import Block from "../src/components/blocks/Block.astro";
import ItemDetail from "../src/components/items/ItemDetail.astro";
import ItemShell from "../src/components/items/ItemShell.astro";
import type { RenderContext } from "../src/lib/render.ts";
import {
  blockVisuals,
  groupItems,
  itemDepth,
  leafVisuals,
  looseVisuals,
  matchesGroup,
  reportPath,
} from "../src/lib/report.ts";
import type { Item, Report } from "../src/lib/types.ts";
import { engineContext, sampleReport, testContext } from "./fixtures.ts";

let container: AstroContainer;
let ctx: RenderContext;
let report: Report;

function item(id: string): Item {
  const found = report.items.find((candidate) => candidate.id === id);
  if (found === undefined) throw new Error(`no item ${id}`);
  return found;
}

beforeAll(async () => {
  container = await AstroContainer.create();
  ctx = await testContext("/PulseAI/");
  report = sampleReport();
});

describe("report helpers", () => {
  const report = sampleReport();
  const research = engineContext().sections.find((section) => section.id === "research");
  if (research === undefined) throw new Error("no research section");
  const items = report.items.filter((item) => item.section === "research");

  it("splits items into deep dives and briefs at deep_dive.min_impact", () => {
    const [deep, brief] = [items.find((i) => i.impact >= 3), items.find((i) => i.impact < 3)];
    expect(deep && itemDepth(deep, 3)).toBe("deep");
    expect(brief && itemDepth(brief, 3)).toBe("brief");
  });

  it("puts each item in the first group it matches, in registry order", () => {
    const groups = groupItems(research, items, report.featured, 3);
    expect(groups.map((g) => [g.group?.id, g.items.map((i) => i.id)])).toEqual([
      ["paper_of_the_day", ["verify-then-expand"]],
      ["top_papers", ["sparse-memory-routing"]],
      ["also_notable", ["tool-use-eval-survey"]],
      ["long_reads", ["agents-in-production-year-one"]],
    ]);
  });

  it("requires every condition of a match", () => {
    const paper = items.find((item) => item.id === "verify-then-expand");
    const group = research.groups.find((g) => g.id === "paper_of_the_day");
    if (paper === undefined || group === undefined) throw new Error("fixture changed");
    expect(matchesGroup(paper, group, report.featured, 3)).toBe(true);
    expect(matchesGroup(paper, group, {}, 3)).toBe(false);
  });

  it("keeps unmatched items after the groups and drops empty groups", () => {
    const article = items.filter((item) => item.type === "article");
    const other = { ...research, groups: research.groups.filter((g) => g.id !== "long_reads") };
    const groups = groupItems(other, article, report.featured, 3);
    expect(groups).toEqual([{ group: undefined, items: article }]);
  });

  it("separates visuals placed in blocks from loose ones", () => {
    const atlas = report.items.find((item) => item.id === "northwind-atlas-3");
    if (atlas === undefined) throw new Error("fixture changed");
    expect(blockVisuals(atlas, "benchmarks").map((v) => v.id)).toEqual(["atlas-3-benchmarks"]);
    expect(looseVisuals(atlas, ["key_facts"]).map((v) => v.id)).toEqual([
      "atlas-3-benchmarks",
      "atlas-price-comparison",
    ]);
  });

  it("maps a date to its route and a dashboard to its leaf visuals", () => {
    expect(reportPath("2026-10-11")).toBe("2026/10/11/");
    const [dashboard] = report.front_page;
    if (dashboard === undefined) throw new Error("fixture changed");
    expect(leafVisuals(dashboard).map((v) => v.kind)).toEqual(["vega-lite", "table"]);
  });
});

describe("item shell", () => {
  it("renders every showcase item with its type's blocks", async () => {
    for (const entry of report.items) {
      const html = await container.renderToString(ItemShell, { props: { ctx, item: entry } });
      expect(html).toContain(`id="${entry.id}"`);
      expect(html).toContain(`data-depth="${entry.impact >= ctx.minImpact ? "deep" : "brief"}"`);
      for (const visual of entry.visuals) {
        if (visual.block !== undefined)
          expect(html, `${entry.id} ${visual.id}`).toContain(`data-block="${visual.block}"`);
      }
    }
  });

  it("shows brief fields instead of blocks below the deep-dive threshold", async () => {
    const html = await container.renderToString(ItemShell, {
      props: { ctx, item: item("quillmark-1-8-4") },
    });
    expect(html).toContain("Quillmark");
    expect(html).not.toContain("data-block=");
  });

  it("links an update to the item it follows up on", async () => {
    const html = await container.renderToString(ItemShell, {
      props: { ctx, item: item("relay-cli-3-0") },
    });
    expect(html).toContain('href="/PulseAI/2026/10/10/#relay-cli-3-rc"');
  });

  it("badges a confidence other than the default", async () => {
    const [signal] = report.signals;
    if (signal === undefined) throw new Error("fixture changed");
    const html = await container.renderToString(ItemShell, { props: { ctx, item: signal } });
    expect(html).toContain("Reported");
    expect(html).toContain("--pulse-color-confidence-reported");
  });
});

describe("item detail", () => {
  it("falls back to GenericDetail for a component that does not exist", async () => {
    const atlas = item("northwind-atlas-3");
    const itemType = { ...ctx.itemType(atlas.type), component: "Missing" } as NonNullable<
      ReturnType<RenderContext["itemType"]>
    >;
    const html = await container.renderToString(ItemDetail, {
      props: { ctx, item: atlas, itemType },
    });
    expect(html).toContain("Northwind Labs");
    expect(html).toContain('data-block="benchmarks"');
  });

  it("renders assigned visuals for a block the component does not know", async () => {
    const atlas = item("northwind-atlas-3");
    const placed = {
      ...atlas,
      visuals: atlas.visuals.map((visual) => ({ ...visual, block: "archive_history" })),
    };
    const html = await container.renderToString(ItemDetail, {
      props: { ctx, item: placed, itemType: ctx.itemType(atlas.type) },
    });
    expect(html).toContain('data-block="archive_history"');
  });

  it("renders nothing for a block with no content and no visuals", async () => {
    const html = await container.renderToString(Block, {
      props: { ctx, item: item("rillet-5-0"), id: "cadence" },
    });
    expect(html.trim()).toBe("");
  });
});
```

Run: `pnpm --filter @pulseai/site test -- items`
Expected: FAIL with `Cannot find module '../src/components/blocks/Block.astro'`.

- [ ] **Step 2: Write the report helpers**

`packages/site/src/lib/report.ts`:

```ts
import type { Section, SectionGroup } from "./context.ts";
import type { Item, LeafVisual, Report, Visual } from "./types.ts";

export type Depth = "deep" | "brief";

/** Items below deep_dive.min_impact render as compact briefs. */
export function itemDepth(item: Item, minImpact: number): Depth {
  return item.impact >= minImpact ? "deep" : "brief";
}

/** Every condition a group's match names must hold. */
export function matchesGroup(
  item: Item,
  group: SectionGroup,
  featured: Report["featured"],
  minImpact: number,
): boolean {
  const { match } = group;
  if (match.featured !== undefined && featured[match.featured] !== item.id) return false;
  if (match.types !== undefined && !match.types.includes(item.type)) return false;
  if (match.depth !== undefined && itemDepth(item, minImpact) !== match.depth) return false;
  return true;
}

export interface ItemGroup {
  /** The registry group, or undefined for items no group matched. */
  group: SectionGroup | undefined;
  items: Item[];
}

/**
 * A section's items split into its registry groups, in registry order. Each item goes to the first
 * group it matches; items that match none come last. Empty groups are dropped.
 */
export function groupItems(
  section: Section,
  items: readonly Item[],
  featured: Report["featured"],
  minImpact: number,
): ItemGroup[] {
  const buckets = section.groups.map((group) => ({ group, items: [] as Item[] }));
  const rest: Item[] = [];
  for (const item of items) {
    const bucket = buckets.find(({ group }) => matchesGroup(item, group, featured, minImpact));
    (bucket?.items ?? rest).push(item);
  }
  const groups: ItemGroup[] = [...buckets, { group: undefined, items: rest }];
  return groups.filter((bucket) => bucket.items.length > 0);
}

/** Items of a section, in report order. */
export function sectionItems(report: Report, sectionId: string): Item[] {
  return report.items.filter((item) => item.section === sectionId);
}

/** Visuals placed in a deep-dive block. */
export function blockVisuals(item: Item, block: string): Visual[] {
  return item.visuals.filter((visual) => visual.block === block);
}

/** Visuals with no block, or whose block the item's type does not render. */
export function looseVisuals(item: Item, blocks: readonly string[]): Visual[] {
  return item.visuals.filter(
    (visual) => visual.block === undefined || !blocks.includes(visual.block),
  );
}

/** "2026-10-11" -> "2026/10/11/", the report's route below the base path. */
export function reportPath(date: string): string {
  return `${date.replaceAll("-", "/")}/`;
}

/** Leaf visuals of a visual: itself, or the visuals inside a dashboard's tiles. */
export function leafVisuals(visual: Visual): LeafVisual[] {
  if (visual.kind !== "dashboard") return [visual];
  return visual.tiles.flatMap((tile) => (tile.tile === "visual" ? [tile.visual] : []));
}
```

- [ ] **Step 3: Write the block primitives**

`packages/site/src/components/blocks/KeyValues.astro`:

```astro
---
export interface Entry {
  label: string;
  value: string | undefined;
}

interface Props {
  entries: readonly Entry[];
}

const entries = Astro.props.entries.filter(
  (entry) => entry.value !== undefined && entry.value !== "",
);
---

{entries.length > 0 && (
  <dl class="kv">
    {entries.map((entry) => (
      <div class="kv__pair">
        <dt>{entry.label}</dt>
        <dd>{entry.value}</dd>
      </div>
    ))}
  </dl>
)}

<style>
  .kv {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(12rem, 100%), 1fr));
    gap: var(--pulse-space-2) var(--pulse-space-4);
  }

  dt {
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-xs);
  }

  dd {
    margin: 0;
    font-weight: var(--pulse-font-weight-medium);
    overflow-wrap: anywhere;
  }
</style>
```

`packages/site/src/components/blocks/Block.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import { blockVisuals } from "../../lib/report.ts";
import type { Item } from "../../lib/types.ts";
import Visual from "../visuals/Visual.astro";

interface Props {
  ctx: RenderContext;
  item: Item;
  /** A block id of the item's type; its title is the locale string blocks.<id>. */
  id: string;
}

// A deep-dive block: its own content (the slot) plus the visuals the report placed in it.
// A block with neither renders nothing.
const { ctx, item, id } = Astro.props;
const visuals = blockVisuals(item, id);
const body = Astro.slots.has("default") ? (await Astro.slots.render("default")).trim() : "";
const titleId = `${item.id}-block-${id}`;
---

{(body !== "" || visuals.length > 0) && (
  <section class="block" data-block={id} aria-labelledby={titleId}>
    <h4 class="item-heading" id={titleId}>{ctx.t(`blocks.${id}`)}</h4>
    {body !== "" && <div class="block__body"><Fragment set:html={body} /></div>}
    {visuals.map((visual) => <Visual ctx={ctx} visual={visual} />)}
  </section>
)}

<style>
  .block {
    display: grid;
    gap: var(--pulse-space-3);
  }

  .block__body {
    display: grid;
    gap: var(--pulse-space-2);
    max-width: var(--pulse-layout-reading-width);
  }

  .block__body :global(ul),
  .block__body :global(ol) {
    display: grid;
    gap: var(--pulse-space-1);
    padding-inline-start: var(--pulse-space-5);
  }
</style>
```

- [ ] **Step 4: Write the item components**

`packages/site/src/components/items/Scores.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { Item } from "../../lib/types.ts";

interface Props {
  ctx: RenderContext;
  item: Item;
}

const { ctx, item } = Astro.props;
const { t } = ctx;
const max = ctx.enums.score.at(-1) ?? item.impact;
const scores = [
  { key: "impact", value: item.impact },
  { key: "novelty", value: item.novelty },
  { key: "relevance", value: item.relevance },
];
---

<span class="scores">
  {scores.map(({ key, value }) => (
    <span class="scores__score" data-score={key}>
      <span class="scores__label">{t(`ui.item.${key}`, { value, max })}</span>
      <span class="scores__pips" aria-hidden="true">
        {ctx.enums.score.map((step) => <span class:list={["scores__pip", { "scores__pip--on": step <= value }]} />)}
      </span>
    </span>
  ))}
</span>

<style>
  .scores {
    display: flex;
    flex-wrap: wrap;
    gap: var(--pulse-space-1) var(--pulse-space-4);
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-xs);
  }

  .scores__score {
    display: inline-flex;
    align-items: center;
    gap: var(--pulse-space-1);
  }

  .scores__pips {
    display: inline-flex;
    gap: calc(var(--pulse-space-1) / 2);
  }

  .scores__pip {
    width: var(--pulse-space-2);
    height: var(--pulse-space-2);
    border-radius: var(--pulse-radius-pill);
    background: var(--pulse-color-border-strong);
  }

  .scores__pip--on {
    background: var(--section-color, var(--pulse-color-accent-default));
  }
</style>
```

`packages/site/src/components/items/Facts.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { Item } from "../../lib/types.ts";

interface Props {
  ctx: RenderContext;
  item: Item;
}

const { ctx, item } = Astro.props;
const { t, fmt } = ctx;
---

<section class="facts" aria-labelledby={`${item.id}-facts`}>
  <h4 class="item-heading" id={`${item.id}-facts`}>{t("ui.item.facts")}</h4>
  <dl class="facts__list">
    {item.facts.map((fact) => (
      <div class="facts__fact">
        <dt>{fact.label}</dt>
        <dd>
          <span class="facts__value">{typeof fact.value === "number" ? fmt.number(fact.value) : fact.value}</span>
          {fact.unit && <span class="facts__unit">{fact.unit}</span>}
          <a class="facts__source" href={`#${item.id}-source-${fact.source_ref}`} aria-label={t("ui.item.fact_source", { n: fact.source_ref + 1 })}>[{fact.source_ref + 1}]</a>
          <q class="facts__quote">{fact.quote}</q>
        </dd>
      </div>
    ))}
  </dl>
</section>

<style>
  .facts__list {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(14rem, 100%), 1fr));
    gap: var(--pulse-space-3);
  }

  .facts__fact {
    padding: var(--pulse-space-3);
    border-inline-start: var(--pulse-border-width-thick) solid var(--section-color, var(--pulse-color-accent-default));
    background: var(--pulse-color-surface-sunken);
    border-radius: var(--pulse-radius-sm);
  }

  dt {
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-xs);
  }

  dd {
    margin: 0;
  }

  .facts__value {
    font-size: var(--pulse-font-size-lg);
    font-weight: var(--pulse-font-weight-semibold);
    font-variant-numeric: tabular-nums;
  }

  .facts__unit {
    margin-inline-start: var(--pulse-space-1);
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
  }

  .facts__source {
    margin-inline-start: var(--pulse-space-1);
    font-size: var(--pulse-font-size-xs);
  }

  .facts__quote {
    display: block;
    margin-block-start: var(--pulse-space-1);
    color: var(--pulse-color-text-muted);
    font-size: var(--pulse-font-size-xs);
  }
</style>
```

`packages/site/src/components/items/Sources.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { Item } from "../../lib/types.ts";
import Badge from "../frame/Badge.astro";

interface Props {
  ctx: RenderContext;
  item: Item;
}

const { ctx, item } = Astro.props;
const { t } = ctx;
---

<section class="sources" aria-labelledby={`${item.id}-sources`}>
  <h4 class="item-heading" id={`${item.id}-sources`}>{t("ui.item.sources")}</h4>
  <ol class="sources__list">
    {item.sources.map((source, index) => (
      <li id={`${item.id}-source-${index}`}>
        <a href={source.url} rel="noopener noreferrer">{source.title}</a>
        <span class="sources__badges">
          <Badge ctx={ctx}>{t(`tiers.${source.tier.toLowerCase()}`)}</Badge>
          <Badge ctx={ctx}>{t(`kinds.${source.kind}`)}</Badge>
        </span>
      </li>
    ))}
  </ol>
</section>

<style>
  .sources__list {
    display: grid;
    gap: var(--pulse-space-2);
    padding-inline-start: var(--pulse-space-5);
    font-size: var(--pulse-font-size-sm);
  }

  .sources__list a {
    overflow-wrap: anywhere;
  }

  .sources__badges {
    display: inline-flex;
    flex-wrap: wrap;
    gap: var(--pulse-space-1);
    margin-inline-start: var(--pulse-space-2);
    vertical-align: middle;
  }
</style>
```

`packages/site/src/components/items/BriefFields.astro`:

```astro
---
import type { ItemType } from "../../lib/context.ts";
import type { RenderContext } from "../../lib/render.ts";
import type { Item } from "../../lib/types.ts";
import KeyValues from "../blocks/KeyValues.astro";

interface Props {
  ctx: RenderContext;
  item: Item;
  itemType: ItemType;
}

// A brief shows the registry's brief_fields; `pulse registry check` guarantees their labels.
const { ctx, item, itemType } = Astro.props;
const detail = item.detail as { [field: string]: unknown };
const entries = itemType.brief_fields.map((field) => ({
  label: ctx.t(`fields.${field}`),
  value: detail[field] === undefined ? undefined : ctx.fmt.value(detail[field], ctx.t),
}));
---

<KeyValues entries={entries} />
```

`packages/site/src/components/items/GenericDetail.astro`:

```astro
---
import type { ItemType } from "../../lib/context.ts";
import { humanize } from "../../lib/i18n.ts";
import type { RenderContext } from "../../lib/render.ts";
import type { Item } from "../../lib/types.ts";
import Block from "../blocks/Block.astro";
import KeyValues from "../blocks/KeyValues.astro";

interface Props {
  ctx: RenderContext;
  item: Item;
  itemType: ItemType;
}

// Every detail field as a labelled value, then the type's blocks with the visuals placed in them.
const { ctx, item, itemType } = Astro.props;
const detail = item.detail as { [field: string]: unknown };
const entries = Object.entries(detail).map(([field, value]) => ({
  label: ctx.t.or(`fields.${field}`, humanize(field)),
  value: ctx.fmt.value(value, ctx.t),
}));
---

<KeyValues entries={entries} />
{itemType.blocks.map((block) => <Block ctx={ctx} item={item} id={block} />)}
```

`packages/site/src/components/items/ItemDetail.astro`:

```astro
---
import type { AstroComponentFactory } from "astro/runtime/server/index.js";
import type { ItemType } from "../../lib/context.ts";
import type { RenderContext } from "../../lib/render.ts";
import type { Item } from "../../lib/types.ts";
import GenericDetail from "./GenericDetail.astro";

interface Props {
  ctx: RenderContext;
  item: Item;
  itemType: ItemType;
}

// The registry names each type's component; files in ./types/ are the components. A type
// without one (an instance's new type, say) still renders through GenericDetail.
const modules = import.meta.glob<{ default: AstroComponentFactory }>("./types/*.astro", {
  eager: true,
});
const components = new Map(
  Object.entries(modules).map(([path, module]) => [
    path.slice(path.lastIndexOf("/") + 1, -".astro".length),
    module.default,
  ]),
);
const { ctx, item, itemType } = Astro.props;
const Component = components.get(itemType.component) ?? GenericDetail;
---

<Component ctx={ctx} item={item} itemType={itemType} />
```

`packages/site/src/components/items/ItemShell.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import { itemDepth, looseVisuals, reportPath } from "../../lib/report.ts";
import type { Item } from "../../lib/types.ts";
import Badge from "../frame/Badge.astro";
import Figure from "../visuals/Figure.astro";
import Visual from "../visuals/Visual.astro";
import BriefFields from "./BriefFields.astro";
import Facts from "./Facts.astro";
import ItemDetail from "./ItemDetail.astro";
import Scores from "./Scores.astro";
import Sources from "./Sources.astro";

interface Props {
  ctx: RenderContext;
  item: Item;
}

const { ctx, item } = Astro.props;
const { t, fmt } = ctx;
// The report loader rejects unknown sections and item types, so both exist.
const section = ctx.section(item.section);
const itemType = ctx.itemType(item.type);
if (section === undefined || itemType === undefined) {
  throw new Error(`item ${item.id}: unknown section or item type`);
}
const depth = itemDepth(item, ctx.minImpact);
const [updateDate, updateItem] = item.update_of?.split("#") ?? [];
// The schema lists the default confidence (confirmed) first; other values earn a badge.
const plainConfidence = ctx.enums.confidence[0];
---

<details
  class="item"
  id={item.id}
  data-item
  data-section={item.section}
  data-type={item.type}
  data-impact={item.impact}
  data-confidence={item.confidence}
  data-update={String(item.update_of !== undefined)}
  data-depth={depth}
  style={`--section-color: ${ctx.cssVar(section.color_token)}`}
>
  <summary class="item__summary">
    <span class="item__kicker">
      <span class="item__section">{t(section.label)}</span>
      <span aria-hidden="true">·</span>
      <span>{t(itemType.label)}</span>
      {updateDate && <Badge ctx={ctx}>{t("ui.item.update")}</Badge>}
      {item.confidence !== plainConfidence && (
        <Badge ctx={ctx} tone={`color.confidence.${item.confidence}`}>{t(`confidence.${item.confidence}`)}</Badge>
      )}
    </span>
    <h3 class="item__title">{item.title}</h3>
    <p class="item__line">{item.summary}</p>
    <Scores ctx={ctx} item={item} />
  </summary>
  <div class="item__body">
    <p class="item__note item__note--why"><strong>{t("ui.item.why")}</strong> {item.why_it_matters}</p>
    {item.what_to_do && (
      <p class="item__note item__note--todo"><strong>{t("ui.item.what_to_do")}</strong> {item.what_to_do}</p>
    )}
    {depth === "deep" ? (
      <ItemDetail ctx={ctx} item={item} itemType={itemType} />
    ) : (
      <BriefFields ctx={ctx} item={item} itemType={itemType} />
    )}
    {depth === "deep" && looseVisuals(item, itemType.blocks).map((visual) => <Visual ctx={ctx} visual={visual} />)}
    {item.facts.length > 0 && <Facts ctx={ctx} item={item} />}
    {item.images.length > 0 && (
      <div class="item__images">{item.images.map((image) => <Figure ctx={ctx} image={image} />)}</div>
    )}
    {item.caveats && (
      <p class="item__note item__note--caveat"><strong>{t("ui.item.caveats")}</strong> {item.caveats}</p>
    )}
    <Sources ctx={ctx} item={item} />
    <p class="item__footer">
      {updateDate && updateItem && (
        <a href={`${ctx.url(reportPath(updateDate))}#${updateItem}`}>{t("ui.item.update_of", { date: fmt.date(updateDate) })}</a>
      )}
      <a class="item__permalink" href={`#${item.id}`}>{t("ui.item.permalink")}</a>
    </p>
  </div>
</details>

<style>
  .item {
    border: var(--pulse-border-width-thin) solid var(--pulse-color-border-subtle);
    border-inline-start: var(--pulse-border-width-thick) solid var(--section-color);
    border-radius: var(--pulse-radius-lg);
    background: var(--pulse-color-surface-raised);
  }

  .item[open] {
    border-color: var(--pulse-color-border-strong);
    border-inline-start-color: var(--section-color);
  }

  .item__summary {
    display: grid;
    gap: var(--pulse-space-2);
    padding: var(--pulse-space-4) var(--pulse-space-5);
    cursor: pointer;
    list-style: none;
  }

  .item__summary::-webkit-details-marker {
    display: none;
  }

  .item__summary::after {
    content: "";
    justify-self: end;
    width: var(--pulse-space-2);
    height: var(--pulse-space-2);
    margin-block-start: calc(-1 * var(--pulse-space-5));
    border-inline-end: var(--pulse-border-width-thick) solid var(--pulse-color-text-muted);
    border-block-end: var(--pulse-border-width-thick) solid var(--pulse-color-text-muted);
    transform: rotate(45deg);
    transition: transform 120ms ease;
  }

  .item[open] > .item__summary::after {
    transform: rotate(-135deg);
  }

  .item__kicker {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--pulse-space-2);
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-xs);
    font-weight: var(--pulse-font-weight-medium);
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }

  .item__section {
    color: var(--pulse-color-text-primary);
  }

  .item__title {
    font-size: var(--pulse-font-size-xl);
  }

  .item[data-depth="brief"] .item__title {
    font-size: var(--pulse-font-size-lg);
  }

  .item__line {
    max-width: var(--pulse-layout-reading-width);
    color: var(--pulse-color-text-secondary);
  }

  .item__body {
    display: grid;
    gap: var(--pulse-space-5);
    padding: 0 var(--pulse-space-5) var(--pulse-space-5);
  }

  .item__note {
    max-width: var(--pulse-layout-reading-width);
  }

  .item__note--why {
    padding-block-start: var(--pulse-space-4);
    border-block-start: var(--pulse-border-width-thin) solid var(--pulse-color-border-subtle);
    font-size: var(--pulse-font-size-lg);
  }

  .item__note--todo,
  .item__note--caveat {
    padding: var(--pulse-space-3) var(--pulse-space-4);
    border-radius: var(--pulse-radius-md);
    background: var(--pulse-color-surface-sunken);
  }

  .item__images {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(16rem, 100%), 1fr));
    gap: var(--pulse-space-4);
  }

  .item__footer {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: var(--pulse-space-3);
    font-size: var(--pulse-font-size-sm);
  }

  .item__permalink {
    margin-inline-start: auto;
  }

  .item :global(.item-heading) {
    margin-block-end: var(--pulse-space-2);
    color: var(--pulse-color-text-secondary);
    font-family: var(--pulse-font-family-body);
    font-size: var(--pulse-font-size-xs);
    font-weight: var(--pulse-font-weight-semibold);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  @media print {
    .item {
      break-inside: avoid-page;
    }

    .item__summary::after {
      display: none;
    }
  }
</style>
```

- [ ] **Step 5: Run the tests**

Run: `pnpm --filter @pulseai/site test && pnpm --filter @pulseai/site typecheck && pnpm demo:check`
Expected: PASS with 0 errors. Every showcase item renders, with each placed visual inside its `data-block` (through `GenericDetail` until Task 11).

- [ ] **Step 6: Commit**

```bash
pnpm biome check --write packages/site && pnpm lint
git add packages/site
git commit -m "feat(site): render items as expandable deep dives and briefs

Each item is a details element with scores, why it matters, its type's
blocks (visuals placed by block id), facts tied to quoted sources, images,
and sources. Items below deep_dive.min_impact show their brief fields; a
type without a component renders through GenericDetail.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 11: Type components and the frame's own charts

**Files:**
- Create: `packages/site/src/components/items/types/{ModelRelease,Release,Paper,Article,Repo,SecurityAdvisory,Industry,LeaderboardShift}.astro`
- Create: `packages/site/src/lib/frame-charts.ts`
- Create: `packages/site/test/types.test.ts`

**Interfaces:**
- Consumes: `Block`, `KeyValues`, `Code`, `Badge`, `VegaLite` (Tasks 7, 8, 10); `ctx.detailSchema(itemType)` and `enumAt`/`rangeAt` (Task 7); detail types (`ItemTypes<Type>Schema.<Type>Detail`, Task 2).
- Produces:
  - One component per registry `component` name. Each renders `itemType.blocks` in registry order through `<Block>`, filling the blocks that have detail fields; visual-only blocks (benchmarks, cadence, timeline, results, figures, …) are filled by placed visuals.
  - Frame charts in `lib/frame-charts.ts`, ordinary `vega-lite` visuals labelled from locales:
    - `archiveHeatmap(days, ctx)`, with cells sized by `chart.heatmap_cell`
    - `researchFunnel(stats, ctx)`, with stages in schema order
    - `rankChanges(id, title, movers, ctx)`
- Enum-ordered output: changelog entries follow the release schema's `tag` enum; the CVSS meter's maximum is the schema's `maximum`; tones come from `color.changelog.*`, `color.ring.*` and `color.severity.*`.

- [ ] **Step 1: Write the failing tests**

`packages/site/test/types.test.ts`:

```ts
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import ItemDetail from "../src/components/items/ItemDetail.astro";
import { archiveHeatmap, rankChanges, researchFunnel } from "../src/lib/frame-charts.ts";
import type { RenderContext } from "../src/lib/render.ts";
import type { Item, Report } from "../src/lib/types.ts";
import { sampleReport, testContext } from "./fixtures.ts";

let container: AstroContainer;
let ctx: RenderContext;
let report: Report;

function item(id: string): Item {
  const found = report.items.find((candidate) => candidate.id === id);
  if (found === undefined) throw new Error(`no item ${id}`);
  return found;
}

async function detail(id: string): Promise<string> {
  const entry = item(id);
  return container.renderToString(ItemDetail, {
    props: { ctx, item: entry, itemType: ctx.itemType(entry.type) },
  });
}

beforeAll(async () => {
  container = await AstroContainer.create();
  ctx = await testContext("/PulseAI/");
  report = sampleReport();
});

describe("type components", () => {
  it("formats a model's key facts with units from the locale", async () => {
    const html = await detail("northwind-atlas-3");
    expect(html).toContain("1,000,000 tokens");
    expect(html).toContain("$2.5 per million tokens");
    expect(html).toContain("Closed");
  });

  it("orders a changelog by the schema's tag order", async () => {
    const html = await detail("relay-cli-3-0");
    const order = ["New", "Fix", "Breaking", "Performance", "Deprecation", "Security"].map((tag) =>
      html.indexOf(`>${tag}</span>`),
    );
    expect(order.every((index) => index >= 0)).toBe(true);
    expect(order).toEqual([...order].sort((a, b) => a - b));
  });

  it("lists a paper's artifacts and marks the missing ones", async () => {
    const html = await detail("verify-then-expand");
    expect(html).toContain("https://example.org/papers/verify-then-expand/code");
    expect(html).toContain("Not released");
    expect(html).toContain("Intermediate");
  });

  it("draws an advisory's CVSS on the schema's scale", async () => {
    const html = await detail("pyfetchkit-path-traversal");
    expect(html).toMatch(/<meter[^>]*max="10"[^>]*value="9.1"/);
    expect(html).toContain("--pulse-color-severity-critical");
  });

  it("draws rank changes as a chart", async () => {
    const html = await detail("open-agents-leaderboard");
    expect(html).toContain('id="visual-open-agents-leaderboard-ranks"');
  });
});

describe("frame charts", () => {
  it("sizes archive cells from a token and labels from locales", () => {
    const visual = archiveHeatmap([{ date: "2026-10-11", score: 45 }], ctx);
    const spec = visual.spec as { width: { step: number }; encoding: { color: { title: string } } };
    expect(spec.width.step).toBe(ctx.tokenNumber("chart.heatmap_cell"));
    expect(spec.encoding.color.title).toBe("Pulse score");
  });

  it("lists funnel stages in the schema's order", () => {
    const visual = researchFunnel(report.meta.stats, ctx);
    const values = (visual.spec as { data: { values: { stage: string; count: number }[] } }).data
      .values;
    expect(values.map((value) => value.stage)).toEqual([
      "Scanned",
      "Triaged",
      "Verified",
      "Published",
    ]);
    expect(visual.alt).toContain("412 scanned");
  });

  it("plots a new entry at its rank after the change only", () => {
    const visual = rankChanges(
      "board",
      "Board",
      [
        { name: "New", after: 1 },
        { name: "Old", before: 1, after: 2 },
      ],
      ctx,
    );
    const values = (visual.spec as { data: { values: { name: string }[] } }).data.values;
    expect(values.filter((value) => value.name === "New")).toHaveLength(1);
    expect(values.filter((value) => value.name === "Old")).toHaveLength(2);
  });
});
```

Run: `pnpm --filter @pulseai/site test -- types`
Expected: FAIL with `Cannot find module '../src/lib/frame-charts.ts'`.

- [ ] **Step 2: Write the frame charts**

`packages/site/src/lib/frame-charts.ts`:

```ts
import type { RenderContext } from "./render.ts";
import type { RunStats, VegaLiteVisual } from "./types.ts";

const VEGA_LITE_SCHEMA = "https://vega.github.io/schema/vega-lite/v6.json";

/**
 * Charts the frame draws from report data (archive heatmap, research funnel, rank changes). They
 * are ordinary vega-lite visuals, themed like every generated chart; labels come from locales.
 */

export interface ArchiveDay {
  date: string;
  score: number;
}

export function archiveHeatmap(days: readonly ArchiveDay[], ctx: RenderContext): VegaLiteVisual {
  const { t } = ctx;
  const cell = ctx.tokenNumber("chart.heatmap_cell");
  return {
    kind: "vega-lite",
    id: "archive-heatmap",
    title: t("ui.archive.heatmap_title"),
    alt: t("ui.archive.heatmap_alt"),
    source_note: t("ui.archive.source"),
    spec: {
      $schema: VEGA_LITE_SCHEMA,
      data: { values: days.map(({ date, score }) => ({ date, score })) },
      // Square day cells, like a contribution calendar.
      width: { step: cell },
      height: { step: cell },
      mark: { type: "rect", cornerRadius: ctx.tokenNumber("chart.bar_corner_radius") },
      encoding: {
        x: {
          field: "date",
          type: "ordinal",
          timeUnit: "yearweek",
          title: null,
          axis: { format: "%b", labelAngle: 0, labelOverlap: "greedy", labelSeparation: 8 },
        },
        y: { field: "date", type: "ordinal", timeUnit: "day", title: null },
        color: { field: "score", type: "quantitative", title: t("ui.score.label") },
        tooltip: [
          { field: "date", type: "temporal", title: t("ui.archive.date") },
          { field: "score", type: "quantitative", title: t("ui.score.label") },
        ],
      },
    },
  };
}

export function researchFunnel(stats: RunStats, ctx: RenderContext): VegaLiteVisual {
  const { t, enums } = ctx;
  const values = enums.stats.map((stage) => ({
    stage: t(`stats.${stage}`),
    count: stats[stage as keyof RunStats],
  }));
  return {
    kind: "vega-lite",
    id: "research-funnel",
    title: t("ui.funnel.title"),
    alt: t(
      "ui.funnel.alt",
      Object.fromEntries(enums.stats.map((stage) => [stage, stats[stage as keyof RunStats]])),
    ),
    source_note: t("ui.funnel.source"),
    spec: {
      $schema: VEGA_LITE_SCHEMA,
      data: { values },
      mark: { type: "bar" },
      encoding: {
        y: { field: "stage", type: "nominal", sort: null, title: null },
        x: { field: "count", type: "quantitative", title: t("ui.funnel.count") },
        tooltip: [
          { field: "stage", type: "nominal", title: t("ui.funnel.stage") },
          { field: "count", type: "quantitative", title: t("ui.funnel.count") },
        ],
      },
    },
  };
}

export interface RankMove {
  name: string;
  before?: number;
  after: number;
}

export function rankChanges(
  id: string,
  title: string,
  movers: readonly RankMove[],
  ctx: RenderContext,
): VegaLiteVisual {
  const { t } = ctx;
  const before = t("fields.before");
  const after = t("fields.after");
  const values = movers.flatMap((move) => [
    ...(move.before === undefined
      ? []
      : [{ name: move.name, when: before, rank: move.before, last: false }]),
    { name: move.name, when: after, rank: move.after, last: true },
  ]);
  return {
    kind: "vega-lite",
    id: `${id}-ranks`,
    title,
    alt: t("ui.leaderboard.alt"),
    source_note: t("ui.leaderboard.source"),
    spec: {
      $schema: VEGA_LITE_SCHEMA,
      data: { values },
      encoding: {
        x: {
          field: "when",
          type: "nominal",
          sort: [before, after],
          title: null,
          axis: { labelAngle: 0 },
        },
        y: {
          field: "rank",
          type: "quantitative",
          scale: { reverse: true, zero: false, nice: false },
          axis: { tickMinStep: 1 },
          title: t("ui.leaderboard.rank_axis"),
        },
      },
      // Series colors mark lines and points only; the direct labels keep the text color.
      layer: [
        {
          mark: { type: "line" },
          encoding: { color: { field: "name", type: "nominal", title: null } },
        },
        {
          mark: { type: "point" },
          encoding: { color: { field: "name", type: "nominal", title: null } },
        },
        {
          transform: [{ filter: { field: "last", equal: true } }],
          mark: { type: "text", align: "left", dx: 8 },
          encoding: { text: { field: "name" } },
        },
      ],
    },
  };
}
```

- [ ] **Step 3: Write the type components**

`packages/site/src/components/items/types/ModelRelease.astro`:

```astro
---
import type { ItemTypesModelReleaseSchema } from "@pulseai/contracts";
import type { ItemType } from "../../../lib/context.ts";
import type { RenderContext } from "../../../lib/render.ts";
import type { Item } from "../../../lib/types.ts";
import Block from "../../blocks/Block.astro";
import KeyValues from "../../blocks/KeyValues.astro";

interface Props {
  ctx: RenderContext;
  item: Item;
  itemType: ItemType;
}

const { ctx, item, itemType } = Astro.props;
const { t, fmt } = ctx;
const d = item.detail as ItemTypesModelReleaseSchema.ModelReleaseDetail;
const price = (value: number | undefined) =>
  value === undefined ? undefined : t("ui.format.usd_per_mtok", { value: fmt.number(value) });
const keyFacts = [
  { label: t("fields.org"), value: d.org },
  { label: t("fields.model"), value: d.model },
  {
    label: t("fields.context_tokens"),
    value:
      d.context_tokens === undefined
        ? undefined
        : t("ui.format.tokens", { value: fmt.number(d.context_tokens) }),
  },
  { label: t("fields.price_in_per_mtok"), value: price(d.price_in_per_mtok) },
  { label: t("fields.price_out_per_mtok"), value: price(d.price_out_per_mtok) },
  { label: t("fields.modalities"), value: d.modalities?.join(", ") },
  { label: t("fields.availability"), value: d.availability?.join(", ") },
  { label: t("fields.weights"), value: t(`weights.${d.weights}`) },
  { label: t("fields.license"), value: d.license },
];
---

{itemType.blocks.map((block) => (
  <Block ctx={ctx} item={item} id={block}>
    {block === "key_facts" && <KeyValues entries={keyFacts} />}
    {block === "try_it" && d.try_it && <p>{d.try_it}</p>}
  </Block>
))}
```

`packages/site/src/components/items/types/Release.astro`:

```astro
---
import type { ItemTypesReleaseSchema } from "@pulseai/contracts";
import type { ItemType } from "../../../lib/context.ts";
import type { RenderContext } from "../../../lib/render.ts";
import { enumAt } from "../../../lib/schema-values.ts";
import type { Item } from "../../../lib/types.ts";
import Block from "../../blocks/Block.astro";
import Code from "../../blocks/Code.astro";
import Badge from "../../frame/Badge.astro";

interface Props {
  ctx: RenderContext;
  item: Item;
  itemType: ItemType;
}

const { ctx, item, itemType } = Astro.props;
const { t } = ctx;
const d = item.detail as ItemTypesReleaseSchema.ReleaseDetail;
// Changelog entries grouped by tag, in the order the schema lists the tags.
const tags = enumAt(ctx.detailSchema(itemType), "properties.changelog.items.properties.tag");
const changelog = [...d.changelog].sort((a, b) => tags.indexOf(a.tag) - tags.indexOf(b.tag));
---

<p class="release-version">
  <span class="release-version__product">{d.product}</span>
  <span class="release-version__number">{d.version}</span>
  {d.previous_version && <span class="muted">{t("ui.release.from", { version: d.previous_version })}</span>}
</p>
{itemType.blocks.map((block) => (
  <Block ctx={ctx} item={item} id={block}>
    {block === "changelog" && (
      <ul class="changelog">
        {changelog.map((entry) => (
          <li>
            <Badge ctx={ctx} tone={`color.changelog.${entry.tag}`}>{t(`changelog.${entry.tag}`)}</Badge>
            <span>{entry.text}</span>
          </li>
        ))}
      </ul>
    )}
    {block === "verdict" && (
      <p><Badge ctx={ctx} tone={`color.ring.${d.verdict}`}>{t(`rings.${d.verdict}`)}</Badge></p>
    )}
    {block === "snippet" && d.snippet && <Code code={d.snippet} />}
    {block === "migration_notes" && d.migration_notes && <p>{d.migration_notes}</p>}
  </Block>
))}

<style>
  .release-version {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--pulse-space-2);
  }

  .release-version__product {
    font-weight: var(--pulse-font-weight-semibold);
  }

  .release-version__number {
    font-family: var(--pulse-font-family-mono);
  }

  .changelog {
    list-style: none;
    padding: 0 !important;
  }

  .changelog li {
    display: grid;
    grid-template-columns: 7rem 1fr;
    align-items: baseline;
    gap: var(--pulse-space-3);
  }

  .changelog :global(.badge) {
    justify-self: start;
  }
</style>
```

`packages/site/src/components/items/types/Paper.astro`:

```astro
---
import type { ItemTypesPaperSchema } from "@pulseai/contracts";
import type { ItemType } from "../../../lib/context.ts";
import type { RenderContext } from "../../../lib/render.ts";
import type { Item } from "../../../lib/types.ts";
import Block from "../../blocks/Block.astro";
import KeyValues from "../../blocks/KeyValues.astro";
import Badge from "../../frame/Badge.astro";

interface Props {
  ctx: RenderContext;
  item: Item;
  itemType: ItemType;
}

const { ctx, item, itemType } = Astro.props;
const { t, fmt } = ctx;
const d = item.detail as ItemTypesPaperSchema.PaperDetail;
const repro = d.reproducibility;
const link = (url: string | undefined, label: string) => ({ url, label });
const artifacts = [
  link(repro.code_url, t("fields.code_url")),
  link(repro.data_url, t("fields.data_url")),
  link(repro.weights_url, t("fields.weights_url")),
];
const guide = d.reading_guide;
const glossary = Object.entries(guide.glossary);
---

<div class="paper-byline">
  <p>{d.authors.join(", ")}</p>
  {d.affiliations && d.affiliations.length > 0 && <p class="muted">{d.affiliations.join(" · ")}</p>}
  <p class="paper-byline__badges">
    <Badge ctx={ctx}>{d.peer_reviewed ? t("ui.paper.peer_reviewed") : t("ui.paper.preprint")}</Badge>
    {d.venue && <Badge ctx={ctx}>{d.venue}</Badge>}
    {d.arxiv_id && <Badge ctx={ctx}>{t("ui.paper.arxiv", { id: d.arxiv_id })}</Badge>}
  </p>
</div>
{itemType.blocks.map((block) => (
  <Block ctx={ctx} item={item} id={block}>
    {block === "tldr" && <p class="paper-lead">{d.tldr}</p>}
    {block === "plain_explanation" && <p>{d.plain_explanation}</p>}
    {block === "problem_and_idea" && (
      <KeyValues entries={[{ label: t("fields.problem"), value: d.problem }, { label: t("fields.key_idea"), value: d.key_idea }]} />
    )}
    {block === "method" && <ol>{d.method_steps.map((step) => <li>{step}</li>)}</ol>}
    {block === "critical_review" && <ul>{d.critical_review.map((point) => <li>{point}</li>)}</ul>}
    {block === "reproducibility" && (
      <ul class="paper-artifacts">
        {artifacts.map((artifact) => (
          <li>
            <span class="muted">{artifact.label}</span>{" "}
            {artifact.url ? <a href={artifact.url} rel="noopener noreferrer">{artifact.url}</a> : t("ui.paper.not_released")}
          </li>
        ))}
        {repro.license && <li><span class="muted">{t("fields.license")}</span> {repro.license}</li>}
      </ul>
    )}
    {block === "takeaway" && <p class="paper-takeaway">{d.takeaway}</p>}
    {block === "reading_guide" && (
      <>
        <KeyValues
          entries={[
            { label: t("fields.reading_minutes"), value: t("ui.paper.minutes", { minutes: fmt.number(guide.reading_minutes) }) },
            { label: t("fields.difficulty"), value: t(`difficulty.${guide.difficulty}`) },
            { label: t("fields.sections"), value: guide.sections.join(", ") },
          ]}
        />
        {glossary.length > 0 && (
          <dl class="paper-glossary">
            {glossary.map(([term, meaning]) => (
              <div><dt>{term}</dt><dd>{meaning}</dd></div>
            ))}
          </dl>
        )}
      </>
    )}
  </Block>
))}

<style>
  .paper-byline {
    display: grid;
    gap: var(--pulse-space-1);
    font-size: var(--pulse-font-size-sm);
  }

  .paper-byline__badges {
    display: flex;
    flex-wrap: wrap;
    gap: var(--pulse-space-2);
  }

  .paper-lead {
    font-family: var(--pulse-font-family-display);
    font-size: var(--pulse-font-size-xl);
    line-height: var(--pulse-font-line-height-tight);
  }

  .paper-takeaway {
    padding: var(--pulse-space-3) var(--pulse-space-4);
    border-inline-start: var(--pulse-border-width-thick) solid var(--section-color);
    background: var(--pulse-color-surface-sunken);
    border-radius: var(--pulse-radius-sm);
    font-weight: var(--pulse-font-weight-medium);
  }

  .paper-artifacts {
    list-style: none;
    padding: 0 !important;
  }

  .paper-artifacts a {
    overflow-wrap: anywhere;
  }

  .paper-glossary {
    display: grid;
    gap: var(--pulse-space-2);
  }

  .paper-glossary dt {
    font-weight: var(--pulse-font-weight-semibold);
  }

  .paper-glossary dd {
    margin: 0;
    color: var(--pulse-color-text-secondary);
  }
</style>
```

`packages/site/src/components/items/types/Article.astro`:

```astro
---
import type { ItemTypesArticleSchema } from "@pulseai/contracts";
import type { ItemType } from "../../../lib/context.ts";
import type { RenderContext } from "../../../lib/render.ts";
import type { Item } from "../../../lib/types.ts";
import Block from "../../blocks/Block.astro";
import KeyValues from "../../blocks/KeyValues.astro";
import Badge from "../../frame/Badge.astro";

interface Props {
  ctx: RenderContext;
  item: Item;
  itemType: ItemType;
}

const { ctx, item, itemType } = Astro.props;
const { t, fmt } = ctx;
const d = item.detail as ItemTypesArticleSchema.ArticleDetail;
---

{itemType.blocks.map((block) => (
  <Block ctx={ctx} item={item} id={block}>
    {block === "key_points" && <ul>{d.key_points.map((point) => <li>{point}</li>)}</ul>}
    {block === "reading_time" && (
      <KeyValues
        entries={[
          { label: t("fields.author"), value: d.author },
          { label: t("fields.publication"), value: d.publication },
          { label: t("fields.reading_minutes"), value: t("ui.paper.minutes", { minutes: fmt.number(d.reading_minutes) }) },
        ]}
      />
    )}
    {block === "verdict" && (
      <p>
        <Badge ctx={ctx} tone={d.worth_full_read ? "color.status.good" : undefined}>
          {t(d.worth_full_read ? "ui.article.full_read_yes" : "ui.article.full_read_no")}
        </Badge>
        {" "}{d.worth_reason}
      </p>
    )}
  </Block>
))}
```

`packages/site/src/components/items/types/Repo.astro`:

```astro
---
import type { ItemTypesRepoSchema } from "@pulseai/contracts";
import type { ItemType } from "../../../lib/context.ts";
import type { RenderContext } from "../../../lib/render.ts";
import type { Item } from "../../../lib/types.ts";
import Block from "../../blocks/Block.astro";
import Code from "../../blocks/Code.astro";
import KeyValues from "../../blocks/KeyValues.astro";

interface Props {
  ctx: RenderContext;
  item: Item;
  itemType: ItemType;
}

const { ctx, item, itemType } = Astro.props;
const { t, fmt } = ctx;
const d = item.detail as ItemTypesRepoSchema.RepoDetail;
const facts = [
  { label: t("fields.full_name"), value: d.full_name },
  { label: t("fields.language"), value: d.language },
  { label: t("fields.license"), value: d.license },
  { label: t("fields.stars"), value: fmt.number(d.stars) },
  {
    label: t("fields.stars_delta_7d"),
    value: d.stars_delta_7d === undefined ? undefined : fmt.signed(d.stars_delta_7d),
  },
  {
    label: t("fields.last_commit"),
    value: d.last_commit === undefined ? undefined : fmt.date(d.last_commit),
  },
];
---

{itemType.blocks.map((block) => (
  <Block ctx={ctx} item={item} id={block}>
    {block === "stars_trend" && d.stars_delta_7d !== undefined && (
      <p>{t("ui.repo.stars_delta", { delta: fmt.signed(d.stars_delta_7d), stars: fmt.number(d.stars) })}</p>
    )}
    {block === "facts" && <KeyValues entries={facts} />}
    {block === "alternatives" && d.alternatives && d.alternatives.length > 0 && (
      <ul>{d.alternatives.map((name) => <li>{name}</li>)}</ul>
    )}
    {block === "quickstart" && d.quickstart && <Code code={d.quickstart} />}
  </Block>
))}
```

`packages/site/src/components/items/types/SecurityAdvisory.astro`:

```astro
---
import type { ItemTypesSecurityAdvisorySchema } from "@pulseai/contracts";
import type { ItemType } from "../../../lib/context.ts";
import type { RenderContext } from "../../../lib/render.ts";
import { rangeAt } from "../../../lib/schema-values.ts";
import type { Item } from "../../../lib/types.ts";
import Block from "../../blocks/Block.astro";
import Code from "../../blocks/Code.astro";
import KeyValues from "../../blocks/KeyValues.astro";
import Badge from "../../frame/Badge.astro";

interface Props {
  ctx: RenderContext;
  item: Item;
  itemType: ItemType;
}

const { ctx, item, itemType } = Astro.props;
const { t, fmt } = ctx;
const d = item.detail as ItemTypesSecurityAdvisorySchema.SecurityAdvisoryDetail;
// The CVSS scale comes from the schema (0 to 10).
const cvssScale = rangeAt(ctx.detailSchema(itemType), "properties.cvss");
const cvssMax = cvssScale.at(-1) ?? 1;
const tone = `color.severity.${d.severity}`;
---

{itemType.blocks.map((block) => (
  <Block ctx={ctx} item={item} id={block}>
    {block === "severity" && (
      <div class="severity" style={`--tone: ${ctx.cssVar(tone)}`}>
        <Badge ctx={ctx} tone={tone}>{t(`severity.${d.severity}`)}</Badge>
        {d.cvss !== undefined && (
          <>
            <p class="severity__score">{t("ui.advisory.cvss", { score: fmt.number(d.cvss) })}</p>
            <meter class="severity__meter" min="0" max={cvssMax} value={d.cvss} aria-label={t("ui.advisory.cvss", { score: fmt.number(d.cvss) })}></meter>
          </>
        )}
        <p class="muted">{d.advisory_id}</p>
      </div>
    )}
    {block === "versions" && (
      <KeyValues entries={[{ label: t("fields.affected"), value: d.affected }, { label: t("fields.fixed_in"), value: d.fixed_in }]} />
    )}
    {block === "exploitation" && (
      <p>
        <Badge ctx={ctx} tone={d.exploited_in_wild ? "color.status.critical" : "color.status.good"}>
          {t(d.exploited_in_wild ? "ui.advisory.exploited" : "ui.advisory.not_exploited")}
        </Badge>
      </p>
    )}
    {block === "fix" && d.fix_command && <Code code={d.fix_command} />}
  </Block>
))}

<style>
  .severity {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--pulse-space-3);
  }

  .severity__score {
    font-weight: var(--pulse-font-weight-semibold);
    font-variant-numeric: tabular-nums;
  }

  .severity__meter {
    inline-size: min(16rem, 100%);
    block-size: var(--pulse-space-3);
    accent-color: var(--tone);
  }

  .severity__meter::-webkit-meter-bar {
    border: 0;
    border-radius: var(--pulse-radius-pill);
    background: var(--pulse-color-surface-sunken);
  }

  .severity__meter::-webkit-meter-optimum-value,
  .severity__meter::-webkit-meter-suboptimum-value,
  .severity__meter::-webkit-meter-even-less-good-value {
    border-radius: var(--pulse-radius-pill);
    background: var(--tone);
  }

  .severity__meter::-moz-meter-bar {
    border-radius: var(--pulse-radius-pill);
    background: var(--tone);
  }
</style>
```

`packages/site/src/components/items/types/Industry.astro`:

```astro
---
import type { ItemTypesIndustrySchema } from "@pulseai/contracts";
import type { ItemType } from "../../../lib/context.ts";
import type { RenderContext } from "../../../lib/render.ts";
import type { Item } from "../../../lib/types.ts";
import Block from "../../blocks/Block.astro";
import KeyValues from "../../blocks/KeyValues.astro";

interface Props {
  ctx: RenderContext;
  item: Item;
  itemType: ItemType;
}

const { ctx, item, itemType } = Astro.props;
const { t } = ctx;
const d = item.detail as ItemTypesIndustrySchema.IndustryDetail;
const summary = [
  { label: t("fields.who"), value: d.who },
  { label: t("fields.what"), value: d.what },
  { label: t("fields.amount"), value: d.amount },
];
---

{itemType.blocks.map((block) => (
  <Block ctx={ctx} item={item} id={block}>
    {block === "summary_facts" && <KeyValues entries={summary} />}
    {block === "builder_impact" && <p>{d.builder_impact}</p>}
  </Block>
))}
```

`packages/site/src/components/items/types/LeaderboardShift.astro`:

```astro
---
import type { ItemTypesLeaderboardShiftSchema } from "@pulseai/contracts";
import type { ItemType } from "../../../lib/context.ts";
import { rankChanges } from "../../../lib/frame-charts.ts";
import type { RenderContext } from "../../../lib/render.ts";
import type { Item } from "../../../lib/types.ts";
import Block from "../../blocks/Block.astro";
import VegaLite from "../../visuals/VegaLite.astro";

interface Props {
  ctx: RenderContext;
  item: Item;
  itemType: ItemType;
}

const { ctx, item, itemType } = Astro.props;
const d = item.detail as ItemTypesLeaderboardShiftSchema.LeaderboardShiftDetail;
---

{itemType.blocks.map((block) => (
  <Block ctx={ctx} item={item} id={block}>
    {block === "rank_changes" && (
      <VegaLite ctx={ctx} visual={rankChanges(item.id, d.board, d.movers, ctx)} />
    )}
    {block === "reliability" && <p>{d.reliability_note}</p>}
  </Block>
))}
```

- [ ] **Step 4: Run the tests**

Run: `pnpm --filter @pulseai/site test && pnpm --filter @pulseai/site typecheck && pnpm demo:check`
Expected: PASS with 0 errors.

- [ ] **Step 5: Commit**

```bash
pnpm biome check --write packages/site && pnpm lint
git add packages/site
git commit -m "feat(site): add deep-dive components for every item type

Model releases, releases, papers, articles, repositories, advisories,
industry news, and leaderboard shifts render their registry blocks in
order; enum order and scales come from the detail schemas. The frame
charts (archive heatmap, research funnel, rank changes) are themed visuals.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 12: Filters, expand and collapse, permalinks, and print

**Files:**
- Create: `packages/site/src/lib/filters.ts`
- Create: `packages/site/src/client/report-controls.ts`
- Create: `packages/site/src/components/frame/FilterBar.astro`
- Create: `packages/site/test/filters.test.ts`

**Interfaces:**
- Consumes: `RenderContext` (Task 7); the item `data-*` attributes and `[data-filter-group]` containers (Tasks 10, 13).
- Produces:
  - `matchesFilters(facets, filters)`, `NO_FILTERS`, `ALL`, `STATUS_NEW`, `STATUS_UPDATES`.
  - `<FilterBar ctx items>`: a hidden `<pulse-report-controls>` that its script reveals.
- Filter options list only what the report holds: sections in registry order, types, the schema's score range, and confidence values in schema order when more than one occurs.
- Behaviour:
  - A container marked `data-filter-group` hides when it has no visible item.
  - The `role="status"` line fills `{shown}`/`{total}` from `data-count-template` (or shows `data-empty-template`).
  - The fragment of the URL opens the item it names, and the `details` around it.
  - `beforeprint` opens every `details` element and `afterprint` restores them; CSS (`::details-content`) expands them in print without JavaScript.

- [ ] **Step 1: Write the failing tests**

`packages/site/test/filters.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { ALL, type ItemFacets, matchesFilters, NO_FILTERS } from "../src/lib/filters.ts";

describe("filters", () => {
  const item: ItemFacets = {
    section: "models",
    type: "paper",
    impact: 3,
    confidence: "confirmed",
    update: false,
  };

  it("passes everything without filters", () => {
    expect(matchesFilters(item, NO_FILTERS)).toBe(true);
  });

  it("applies each filter", () => {
    expect(matchesFilters(item, { ...NO_FILTERS, section: "oss" })).toBe(false);
    expect(matchesFilters(item, { ...NO_FILTERS, type: "paper" })).toBe(true);
    expect(matchesFilters(item, { ...NO_FILTERS, minImpact: 4 })).toBe(false);
    expect(matchesFilters(item, { ...NO_FILTERS, confidence: "reported" })).toBe(false);
    expect(matchesFilters(item, { ...NO_FILTERS, status: "updates" })).toBe(false);
    expect(matchesFilters({ ...item, update: true }, { ...NO_FILTERS, status: "new" })).toBe(false);
    expect(matchesFilters(item, { ...NO_FILTERS, section: ALL, status: ALL })).toBe(true);
  });
});
```

Run: `pnpm --filter @pulseai/site test -- filters`
Expected: FAIL with `Cannot find module '../src/lib/filters.ts'`.

- [ ] **Step 2: Write the filter logic**

`packages/site/src/lib/filters.ts`:

```ts
/** Filter values; ALL means "no restriction" for a select. */
export const ALL = "all";
export const STATUS_NEW = "new";
export const STATUS_UPDATES = "updates";

/** What the filter row can see of one item (from its data-* attributes). */
export interface ItemFacets {
  section: string;
  type: string;
  impact: number;
  confidence: string;
  update: boolean;
}

export interface Filters {
  section: string;
  type: string;
  minImpact: number;
  confidence: string;
  status: string;
}

export const NO_FILTERS: Filters = {
  section: ALL,
  type: ALL,
  minImpact: 1,
  confidence: ALL,
  status: ALL,
};

export function matchesFilters(facets: ItemFacets, filters: Filters): boolean {
  if (filters.section !== ALL && facets.section !== filters.section) return false;
  if (filters.type !== ALL && facets.type !== filters.type) return false;
  if (facets.impact < filters.minImpact) return false;
  if (filters.confidence !== ALL && facets.confidence !== filters.confidence) return false;
  if (filters.status === STATUS_NEW && facets.update) return false;
  if (filters.status === STATUS_UPDATES && !facets.update) return false;
  return true;
}
```

- [ ] **Step 3: Write the controls**

`packages/site/src/client/report-controls.ts`:

```ts
import { type Filters, type ItemFacets, matchesFilters, NO_FILTERS } from "../lib/filters.ts";

const ITEM = "details[data-item]";

function facets(item: HTMLElement): ItemFacets {
  const { section = "", type = "", impact = "0", confidence = "", update = "false" } = item.dataset;
  return { section, type, impact: Number(impact), confidence, update: update === "true" };
}

function value(form: HTMLFormElement, name: string, fallback: string): string {
  const field = form.elements.namedItem(name);
  return field instanceof HTMLSelectElement ? field.value : fallback;
}

/** Open the item a URL fragment names (and the details around it), then scroll to it. */
function openTarget(hash: string): void {
  if (hash.length < 2) return;
  const target = document.getElementById(decodeURIComponent(hash.slice(1)));
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
    // A group or section with nothing left to show disappears with its heading.
    for (const container of document.querySelectorAll<HTMLElement>("[data-filter-group]")) {
      container.hidden = container.querySelector(`${ITEM}:not([hidden])`) === null;
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
```

`packages/site/src/components/frame/FilterBar.astro`:

```astro
---
import { ALL, STATUS_NEW, STATUS_UPDATES } from "../../lib/filters.ts";
import type { RenderContext } from "../../lib/render.ts";
import type { Item } from "../../lib/types.ts";

interface Props {
  ctx: RenderContext;
  items: readonly Item[];
}

// Options list only what this report holds, in registry and schema order.
const { ctx, items } = Astro.props;
const { t } = ctx;
const present = (values: Iterable<string>) => new Set(values);
const sections = present(items.map((item) => item.section));
const types = present(items.map((item) => item.type));
const confidences = present(items.map((item) => item.confidence));
const sectionOptions = ctx.sections.filter((section) => sections.has(section.id));
const typeOptions = [...types]
  .map((id) => ctx.itemType(id))
  .filter((itemType) => itemType !== undefined);
const confidenceOptions = ctx.enums.confidence.filter((value) => confidences.has(value));
---

<pulse-report-controls class="filters" hidden data-print="hide">
  <form class="filters__form" aria-label={t("ui.filters.title")}>
    <div class="filters__field">
      <label for="filter-section">{t("ui.filters.section")}</label>
      <select id="filter-section" name="section">
        <option value={ALL}>{t("ui.filters.all")}</option>
        {sectionOptions.map((section) => <option value={section.id}>{t(section.label)}</option>)}
      </select>
    </div>
    <div class="filters__field">
      <label for="filter-type">{t("ui.filters.type")}</label>
      <select id="filter-type" name="type">
        <option value={ALL}>{t("ui.filters.all")}</option>
        {typeOptions.map((itemType) => <option value={itemType.id}>{t(itemType.label)}</option>)}
      </select>
    </div>
    <div class="filters__field">
      <label for="filter-min_impact">{t("ui.filters.min_impact")}</label>
      <select id="filter-min_impact" name="min_impact">
        {ctx.enums.score.map((score) => <option value={score}>{t("ui.filters.impact_at_least", { value: score })}</option>)}
      </select>
    </div>
    {confidenceOptions.length > 1 && (
      <div class="filters__field">
        <label for="filter-confidence">{t("ui.filters.confidence")}</label>
        <select id="filter-confidence" name="confidence">
          <option value={ALL}>{t("ui.filters.all")}</option>
          {confidenceOptions.map((value) => <option value={value}>{t(`confidence.${value}`)}</option>)}
        </select>
      </div>
    )}
    <div class="filters__field">
      <label for="filter-status">{t("ui.filters.status")}</label>
      <select id="filter-status" name="status">
        <option value={ALL}>{t("ui.filters.all")}</option>
        <option value={STATUS_NEW}>{t("ui.filters.new")}</option>
        <option value={STATUS_UPDATES}>{t("ui.filters.updates")}</option>
      </select>
    </div>
    <div class="filters__actions">
      <button class="button" type="reset">{t("ui.filters.reset")}</button>
      <button class="button" type="button" data-expand-all>{t("ui.filters.expand_all")}</button>
      <button class="button" type="button" data-collapse-all>{t("ui.filters.collapse_all")}</button>
    </div>
  </form>
  <p
    class="filters__status"
    role="status"
    data-filter-status
    data-count-template={t("ui.filters.count")}
    data-empty-template={t("ui.filters.no_match")}
  ></p>
</pulse-report-controls>

<script>
  import "../../client/report-controls.ts";
</script>

<style>
  .filters {
    display: grid;
    gap: var(--pulse-space-2);
    margin-block: var(--pulse-space-6) var(--pulse-space-4);
    padding: var(--pulse-space-3) var(--pulse-space-4);
    border: var(--pulse-border-width-thin) solid var(--pulse-color-border-subtle);
    border-radius: var(--pulse-radius-lg);
    background: var(--pulse-color-surface-raised);
  }

  .filters__form {
    display: flex;
    flex-wrap: wrap;
    align-items: end;
    gap: var(--pulse-space-3);
  }

  .filters__field {
    display: grid;
    gap: var(--pulse-space-1);
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-xs);
  }

  select {
    min-width: 8rem;
    padding: var(--pulse-space-1) var(--pulse-space-2);
    border: var(--pulse-border-width-thin) solid var(--pulse-color-border-strong);
    border-radius: var(--pulse-radius-md);
    background: var(--pulse-color-surface-raised);
    color: var(--pulse-color-text-primary);
    font: inherit;
    font-size: var(--pulse-font-size-sm);
  }

  .filters__actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--pulse-space-2);
    margin-inline-start: auto;
  }

  .filters__status {
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-xs);
  }
</style>
```

- [ ] **Step 4: Run the tests**

Run: `pnpm --filter @pulseai/site test && pnpm --filter @pulseai/site typecheck && pnpm demo:check`
Expected: PASS with 0 errors. Task 15's end-to-end tests drive the controls in a browser.

- [ ] **Step 5: Commit**

```bash
pnpm biome check --write packages/site && pnpm lint
git add packages/site
git commit -m "feat(site): add item filters, expand and collapse, and permalinks

Filter by section, type, minimum impact, confidence, and new or update;
the count and empty state come from locale templates. A URL fragment opens
its item, and printing expands every item.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 13: The report view, the front page, and dated editions

**Files:**
- Create: `packages/site/src/components/frame/{ReportSection,SectionNotes,Signals,Corrections,Methodology,ReportView}.astro`
- Create: `packages/site/src/pages/[year]/[month]/[day]/index.astro`
- Modify: `packages/site/src/pages/index.astro` (replace the Task 7 placeholder)
- Create: `packages/site/test/report-view.test.ts`

**Interfaces:**
- Consumes: Tasks 7–12. `groupItems` and `sectionItems` come from Task 10, `researchFunnel` from Task 11, `FilterBar` from Task 12.
- Produces:
  - `<ReportView ctx report searchable?>`: the fixed frame of spec §12.2. Its `<article>` carries `data-pagefind-body` only when `searchable` (default `true`).
  - Routes `/` (the latest edition, kept out of search, with a canonical link to its dated page) and `/YYYY/MM/DD/` (every edition).
  - `<ReportSection>` is a `[data-filter-group]` that shows its registry groups, or "Other" for leftovers when the section has groups. Its section notes render where `note.group` names a group, otherwise after the groups.
  - `<Signals>` is a filter group too; reported items show their confidence badge there.

- [ ] **Step 1: Write the failing tests**

`packages/site/test/report-view.test.ts`:

```ts
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import Corrections from "../src/components/frame/Corrections.astro";
import ReportView from "../src/components/frame/ReportView.astro";
import Signals from "../src/components/frame/Signals.astro";
import type { RenderContext } from "../src/lib/render.ts";
import type { Report } from "../src/lib/types.ts";
import { sampleReport, testContext } from "./fixtures.ts";

let container: AstroContainer;
let ctx: RenderContext;
let report: Report;

beforeAll(async () => {
  container = await AstroContainer.create();
  ctx = await testContext("/PulseAI/");
  report = sampleReport();
});

describe("report view", () => {
  it("renders nothing for empty signals and corrections", async () => {
    expect((await container.renderToString(Signals, { props: { ctx, signals: [] } })).trim()).toBe(
      "",
    );
    expect(
      (await container.renderToString(Corrections, { props: { ctx, corrections: [] } })).trim(),
    ).toBe("");
  });

  it("renders sections in registry order with the research groups", async () => {
    const html = await container.renderToString(ReportView, { props: { ctx, report } });
    const sections = ctx.sections.map((section) => html.indexOf(`id="section-${section.id}"`));
    expect(sections.every((index) => index >= 0)).toBe(true);
    expect(sections).toEqual([...sections].sort((a, b) => a - b));
    for (const group of ["Paper of the day", "Top papers", "Also notable", "Long reads"]) {
      expect(html).toContain(group);
    }
    expect(html).toContain("data-pagefind-body");
  });

  it("keeps the front page out of the search index", async () => {
    const html = await container.renderToString(ReportView, {
      props: { ctx, report, searchable: false },
    });
    expect(html).not.toContain("data-pagefind-body");
  });
});
```

Run: `pnpm --filter @pulseai/site test -- report-view`
Expected: FAIL with `Cannot find module '../src/components/frame/Corrections.astro'`.

- [ ] **Step 2: Write the components**

`packages/site/src/components/frame/SectionNotes.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { SectionNote } from "../../lib/types.ts";

interface Props {
  ctx: RenderContext;
  notes: readonly SectionNote[];
}

const { ctx, notes } = Astro.props;
const { t } = ctx;
---

{notes.length > 0 && (
  <aside class="notes" aria-label={t("ui.section.notes")}>
    {notes.map((note) => (
      <p class="notes__note">
        <strong>{note.title}</strong> {note.text}{" "}
        {note.url && <a href={note.url} rel="noopener noreferrer">{t("ui.section.note_link")}</a>}
      </p>
    ))}
  </aside>
)}

<style>
  .notes {
    display: grid;
    gap: var(--pulse-space-2);
    padding: var(--pulse-space-4);
    border: var(--pulse-border-width-thin) dashed var(--pulse-color-border-strong);
    border-radius: var(--pulse-radius-lg);
    font-size: var(--pulse-font-size-sm);
  }
</style>
```

`packages/site/src/components/frame/ReportSection.astro`:

```astro
---
import type { Section } from "../../lib/context.ts";
import type { RenderContext } from "../../lib/render.ts";
import { groupItems } from "../../lib/report.ts";
import type { Item, Report, SectionNote } from "../../lib/types.ts";
import ItemShell from "../items/ItemShell.astro";
import SectionNotes from "./SectionNotes.astro";

interface Props {
  ctx: RenderContext;
  section: Section;
  items: readonly Item[];
  featured: Report["featured"];
  notes: readonly SectionNote[];
}

const { ctx, section, items, featured, notes } = Astro.props;
const { t } = ctx;
const groups = groupItems(section, items, featured, ctx.minImpact);
// A section without registry groups lists its items directly; one with groups names the rest.
const hasGroups = section.groups.length > 0;
const groupNotes = (id: string | undefined) => notes.filter((note) => note.group === id);
---

{(items.length > 0 || notes.length > 0) && (
  <section
    class="report-section"
    id={`section-${section.id}`}
    aria-labelledby={`section-${section.id}-title`}
    data-filter-group
    style={`--section-color: ${ctx.cssVar(section.color_token)}`}
  >
    <h2 class="report-section__title" id={`section-${section.id}-title`}>{t(section.label)}</h2>
    {groups.map(({ group, items: groupItemsList }) => (
      <div class="report-section__group" data-filter-group>
        {hasGroups && (
          <h3 class="report-section__group-title">{group ? t(group.label) : t("ui.section.other")}</h3>
        )}
        <div class="report-section__items">
          {groupItemsList.map((item) => <ItemShell ctx={ctx} item={item} />)}
        </div>
        {group && <SectionNotes ctx={ctx} notes={groupNotes(group.id)} />}
      </div>
    ))}
    <SectionNotes ctx={ctx} notes={groupNotes(undefined)} />
  </section>
)}

<style>
  .report-section {
    display: grid;
    gap: var(--pulse-space-5);
    margin-block: var(--pulse-space-8);
  }

  .report-section__title {
    display: flex;
    align-items: center;
    gap: var(--pulse-space-3);
    padding-block-end: var(--pulse-space-2);
    border-block-end: var(--pulse-border-width-thin) solid var(--pulse-color-border-strong);
    font-size: var(--pulse-font-size-2xl);
  }

  .report-section__title::before {
    content: "";
    flex: none;
    width: var(--pulse-space-4);
    height: var(--pulse-space-4);
    border-radius: var(--pulse-radius-sm);
    background: var(--section-color);
  }

  .report-section__group {
    display: grid;
    gap: var(--pulse-space-3);
  }

  .report-section__group-title {
    color: var(--pulse-color-text-secondary);
    font-family: var(--pulse-font-family-body);
    font-size: var(--pulse-font-size-sm);
    font-weight: var(--pulse-font-weight-semibold);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .report-section__items {
    display: grid;
    gap: var(--pulse-space-3);
  }
</style>
```

`packages/site/src/components/frame/Signals.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import type { Item } from "../../lib/types.ts";
import ItemShell from "../items/ItemShell.astro";

interface Props {
  ctx: RenderContext;
  signals: readonly Item[];
}

const { ctx, signals } = Astro.props;
const { t } = ctx;
---

{signals.length > 0 && (
  <section class="region signals" aria-labelledby="signals-title" data-filter-group>
    <h2 class="region__title" id="signals-title">{t("ui.signals.title")}</h2>
    <p class="signals__intro muted">{t("ui.signals.intro")}</p>
    <div class="signals__items">
      {signals.map((item) => <ItemShell ctx={ctx} item={item} />)}
    </div>
  </section>
)}

<style>
  .signals {
    padding: var(--pulse-space-5);
    border: var(--pulse-border-width-thin) dashed var(--pulse-color-border-strong);
    border-radius: var(--pulse-radius-lg);
    background: var(--pulse-color-surface-sunken);
  }

  .signals__intro {
    margin-block-end: var(--pulse-space-4);
  }

  .signals__items {
    display: grid;
    gap: var(--pulse-space-3);
  }
</style>
```

`packages/site/src/components/frame/Corrections.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import { reportPath } from "../../lib/report.ts";
import type { Report } from "../../lib/types.ts";

interface Props {
  ctx: RenderContext;
  corrections: Report["corrections"];
}

const { ctx, corrections } = Astro.props;
const { t, fmt } = ctx;
---

{corrections.length > 0 && (
  <section class="region" aria-labelledby="corrections-title">
    <h2 class="region__title" id="corrections-title">{t("ui.corrections.title")}</h2>
    <ul class="corrections">
      {corrections.map((correction) => (
        <li>
          <a href={`${ctx.url(reportPath(correction.report_date))}#${correction.item_id}`}>
            {t("ui.corrections.entry", { date: fmt.date(correction.report_date) })}
          </a>
          {" "}{correction.text}
        </li>
      ))}
    </ul>
  </section>
)}

<style>
  .corrections {
    display: grid;
    gap: var(--pulse-space-2);
    max-width: var(--pulse-layout-reading-width);
    padding-inline-start: var(--pulse-space-5);
  }
</style>
```

`packages/site/src/components/frame/Methodology.astro`:

```astro
---
import { researchFunnel } from "../../lib/frame-charts.ts";
import type { RenderContext } from "../../lib/render.ts";
import type { Report } from "../../lib/types.ts";
import DataTable from "../visuals/DataTable.astro";
import VegaLite from "../visuals/VegaLite.astro";
import Badge from "./Badge.astro";

interface Props {
  ctx: RenderContext;
  report: Report;
}

const { ctx, report } = Astro.props;
const { t, fmt } = ctx;
const { meta, methodology } = report;
const models = Object.entries(meta.models).map(([role, model]) => `${role}: ${model}`);
---

<section class="region methodology" aria-labelledby="methodology-title">
  <h2 class="region__title" id="methodology-title">{t("ui.methodology.title")}</h2>
  <div class="methodology__grid">
    <div class="flow">
      {methodology.notes.length > 0 && (
        <ul class="methodology__notes">{methodology.notes.map((note) => <li>{note}</li>)}</ul>
      )}
      <dl class="methodology__run">
        <div><dt>{t("ui.run.engine")}</dt><dd>{meta.engine_version}</dd></div>
        <div><dt>{t("ui.run.host")}</dt><dd>{t(`hosts.${meta.host}`)}</dd></div>
        <div><dt>{t("ui.run.cost")}</dt><dd>{meta.cost_usd === null ? t("ui.run.cost_unknown") : t("ui.format.usd", { value: fmt.number(meta.cost_usd, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) })}</dd></div>
        {models.length > 0 && <div><dt>{t("ui.run.models")}</dt><dd>{models.join(", ")}</dd></div>}
      </dl>
    </div>
    <VegaLite ctx={ctx} visual={researchFunnel(meta.stats, ctx)} />
  </div>
  {meta.source_health.length > 0 && (
    <section class="flow" aria-labelledby="health-title">
      <h3 class="methodology__subtitle" id="health-title">{t("ui.health.title")}</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">{t("ui.health.source")}</th>
              <th scope="col">{t("ui.health.status")}</th>
              <th scope="col" class="num">{t("ui.health.items")}</th>
            </tr>
          </thead>
          <tbody>
            {meta.source_health.map((source) => (
              <tr>
                <td><code>{source.source_id}</code></td>
                <td>
                  <Badge ctx={ctx} tone={source.ok ? "color.status.good" : "color.status.critical"}>
                    {t(source.ok ? "ui.health.ok" : "ui.health.failed")}
                  </Badge>
                  {source.error && <span class="muted"> {source.error}</span>}
                </td>
                <td class="num">{fmt.number(source.items)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )}
  {methodology.rejected.length > 0 && (
    <section class="flow" aria-labelledby="rejected-title">
      <h3 class="methodology__subtitle" id="rejected-title">{t("ui.methodology.rejected")}</h3>
      <DataTable
        ctx={ctx}
        caption={t("ui.methodology.rejected")}
        hideCaption
        columns={[t("ui.methodology.item"), t("ui.methodology.reason")]}
        rows={methodology.rejected.map((entry) => [entry.title, entry.reason])}
      />
    </section>
  )}
</section>

<style>
  .methodology {
    display: grid;
    gap: var(--pulse-space-5);
    padding-block-start: var(--pulse-space-5);
    border-block-start: var(--pulse-border-width-thick) solid var(--pulse-color-text-primary);
  }

  .methodology__grid {
    display: grid;
    gap: var(--pulse-space-5);
  }

  @media (min-width: 56rem) {
    .methodology__grid {
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      align-items: start;
    }
  }

  .methodology__notes {
    display: grid;
    gap: var(--pulse-space-2);
    padding-inline-start: var(--pulse-space-5);
  }

  .methodology__run {
    display: grid;
    gap: var(--pulse-space-2);
    font-size: var(--pulse-font-size-sm);
  }

  .methodology__run dt {
    color: var(--pulse-color-text-secondary);
  }

  .methodology__run dd {
    margin: 0;
    overflow-wrap: anywhere;
  }

  .methodology__subtitle {
    font-size: var(--pulse-font-size-lg);
  }
</style>
```

`packages/site/src/components/frame/ReportView.astro`:

```astro
---
import type { RenderContext } from "../../lib/render.ts";
import { sectionItems } from "../../lib/report.ts";
import type { Report } from "../../lib/types.ts";
import ActionList from "./ActionList.astro";
import AdoptionRadar from "./AdoptionRadar.astro";
import Corrections from "./Corrections.astro";
import FilterBar from "./FilterBar.astro";
import FrontPage from "./FrontPage.astro";
import KpiTiles from "./KpiTiles.astro";
import Masthead from "./Masthead.astro";
import Methodology from "./Methodology.astro";
import ReportSection from "./ReportSection.astro";
import Signals from "./Signals.astro";
import Tldr from "./Tldr.astro";

interface Props {
  ctx: RenderContext;
  report: Report;
  /** Index this view for search; the front page repeats the latest edition, so it is not. */
  searchable?: boolean;
}

// The fixed frame (spec 12.2): masthead, numbers, TL;DR, front page, radar, sections in registry
// order, actions, signals, corrections, methodology.
const { ctx, report, searchable = true } = Astro.props;
---

<article class="report" data-pagefind-body={searchable ? "" : undefined} data-report={report.meta.date}>
  <Masthead ctx={ctx} report={report} />
  <KpiTiles ctx={ctx} kpis={report.kpis} />
  <Tldr ctx={ctx} lines={report.tldr} />
  <FrontPage ctx={ctx} visuals={report.front_page} />
  <AdoptionRadar ctx={ctx} entries={report.adoption_radar} items={report.items} />
  {report.items.length > 0 && <FilterBar ctx={ctx} items={[...report.items, ...report.signals]} />}
  {ctx.sections.map((section) => (
    <ReportSection
      ctx={ctx}
      section={section}
      items={sectionItems(report, section.id)}
      featured={report.featured}
      notes={report.section_notes[section.id] ?? []}
    />
  ))}
  <ActionList ctx={ctx} actions={report.action_list} />
  <Signals ctx={ctx} signals={report.signals} />
  <Corrections ctx={ctx} corrections={report.corrections} />
  <Methodology ctx={ctx} report={report} />
</article>
```

- [ ] **Step 3: Write the pages**

Replace `packages/site/src/pages/index.astro`:

```astro
---
import EmptyState from "../components/frame/EmptyState.astro";
import ReportView from "../components/frame/ReportView.astro";
import Base from "../layouts/Base.astro";
import { reportPath } from "../lib/report.ts";
import { allReports } from "../lib/reports.ts";
import { getSite } from "../lib/site-data.ts";

const { ctx } = getSite();
const [latest] = await allReports();
---

<Base
  title={latest ? `${latest.headline} · ${ctx.t("ui.site.title")}` : ctx.t("ui.site.title")}
  description={latest?.headline}
  canonical={latest ? reportPath(latest.meta.date) : undefined}
>
  {latest ? <ReportView ctx={ctx} report={latest} searchable={false} /> : <EmptyState ctx={ctx} />}
</Base>
```

`packages/site/src/pages/[year]/[month]/[day]/index.astro`:

```astro
---
import type { GetStaticPaths } from "astro";
import ReportView from "../../../../components/frame/ReportView.astro";
import Base from "../../../../layouts/Base.astro";
import { allReports } from "../../../../lib/reports.ts";
import { getSite } from "../../../../lib/site-data.ts";
import type { Report } from "../../../../lib/types.ts";

export const getStaticPaths = (async () => {
  const reports = await allReports();
  return reports.map((report) => {
    const [year, month, day] = report.meta.date.split("-");
    return { params: { year, month, day }, props: { report } };
  });
}) satisfies GetStaticPaths;

interface Props {
  report: Report;
}

const { report } = Astro.props;
const { ctx } = getSite();
---

<Base title={`${report.headline} · ${ctx.t("ui.site.title")}`} description={report.headline}>
  <ReportView ctx={ctx} report={report} />
</Base>
```

- [ ] **Step 4: Run the tests and build**

Run: `pnpm --filter @pulseai/site test && pnpm --filter @pulseai/site typecheck && pnpm demo:build && pnpm demo:check`
Expected: all tests pass, 0 check errors, and `index.html` plus `2026/10/09/`, `2026/10/10/` and `2026/10/11/` are built.

Run: `pnpm demo:preview` and open `http://127.0.0.1:4321/PulseAI/` in a browser.
Expected: the 2026-10-11 showcase renders the full frame in the order listed under Interfaces, every chart and diagram draws, and Auto/Light/Dark switch the page and the charts together. Stop the server afterwards.

- [ ] **Step 5: Commit**

```bash
pnpm biome check --write packages/site && pnpm lint
git add packages/site
git commit -m "feat(site): render full editions at / and /YYYY/MM/DD/

The report view composes the fixed frame: sections in registry order with
their groups and notes, actions, signals, corrections, and methodology with
the research funnel, source health, and rejected items. The front page
repeats the latest edition, out of the search index.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 14: Archive and feed

**Files:**
- Create: `packages/site/src/pages/archive/index.astro`
- Create: `packages/site/src/pages/[feed].ts`

**Interfaces:**
- Consumes: `allReports`, `getSite`, `reportPath`, `archiveHeatmap`, `VegaLite` (Tasks 7–11).
- Produces:
  - `/archive/`: the heatmap of Pulse scores plus every edition grouped by month, newest first.
  - `/rss.xml`, only when `config.site.url` is set, since a feed needs absolute links. Each item links to `<site>/<base>YYYY/MM/DD/`.
  - The sitemap comes from `@astrojs/sitemap` under the same condition (configured in Task 7), and search from Pagefind (Task 7). Only report articles marked `data-pagefind-body` are indexed.

- [ ] **Step 1: Add the feed library**

Run: `pnpm --filter @pulseai/site add @astrojs/rss`

- [ ] **Step 2: Write the archive and the feed**

`packages/site/src/pages/archive/index.astro`:

```astro
---
import VegaLite from "../../components/visuals/VegaLite.astro";
import Base from "../../layouts/Base.astro";
import { archiveHeatmap } from "../../lib/frame-charts.ts";
import { reportPath } from "../../lib/report.ts";
import { allReports } from "../../lib/reports.ts";
import { getSite } from "../../lib/site-data.ts";

const { ctx } = getSite();
const { t, fmt } = ctx;
const reports = await allReports();
const days = reports.map((report) => ({ date: report.meta.date, score: report.pulse_score.value }));
// Group by month (YYYY-MM), newest first.
const months = new Map<string, typeof reports>();
for (const report of reports) {
  const month = report.meta.date.slice(0, 7);
  months.set(month, [...(months.get(month) ?? []), report]);
}
const monthTitle = (month: string) =>
  new Intl.DateTimeFormat(ctx.lang, { month: "long", year: "numeric", timeZone: "UTC" }).format(
    new Date(`${month}-01T00:00:00Z`),
  );
---

<Base title={`${t("ui.archive.title")} · ${t("ui.site.title")}`}>
  <header class="archive-header">
    <h1>{t("ui.archive.title")}</h1>
    <p class="muted">{t("ui.archive.count", { count: fmt.number(reports.length) })}</p>
  </header>
  {days.length > 0 && <VegaLite ctx={ctx} visual={archiveHeatmap(days, ctx)} />}
  {[...months].map(([month, monthReports]) => (
    <section class="archive-month" aria-labelledby={`month-${month}`}>
      <h2 id={`month-${month}`}>{monthTitle(month)}</h2>
      <ol class="archive-list">
        {monthReports.map((report) => (
          <li>
            <a href={ctx.url(reportPath(report.meta.date))}>
              <time datetime={report.meta.date}>{fmt.date(report.meta.date)}</time>
              <span class="archive-list__headline">{report.headline}</span>
            </a>
            <span class="archive-list__score">{t("ui.archive.score", { score: fmt.number(report.pulse_score.value) })}</span>
          </li>
        ))}
      </ol>
    </section>
  ))}
</Base>

<style>
  .archive-header {
    display: grid;
    gap: var(--pulse-space-2);
    padding-block: var(--pulse-space-7) var(--pulse-space-5);
  }

  .archive-header h1 {
    font-size: var(--pulse-font-size-3xl);
  }

  .archive-month {
    margin-block: var(--pulse-space-6);
  }

  .archive-month h2 {
    margin-block-end: var(--pulse-space-3);
    font-size: var(--pulse-font-size-xl);
  }

  .archive-list {
    display: grid;
    gap: var(--pulse-space-2);
    padding: 0;
    list-style: none;
  }

  .archive-list li {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--pulse-space-2) var(--pulse-space-4);
    padding: var(--pulse-space-3) var(--pulse-space-4);
    border: var(--pulse-border-width-thin) solid var(--pulse-color-border-subtle);
    border-radius: var(--pulse-radius-md);
    background: var(--pulse-color-surface-raised);
  }

  .archive-list a {
    display: grid;
    gap: var(--pulse-space-1);
    text-decoration: none;
  }

  .archive-list time {
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
  }

  .archive-list__headline {
    color: var(--pulse-color-text-primary);
    font-family: var(--pulse-font-family-display);
    font-size: var(--pulse-font-size-lg);
    font-weight: var(--pulse-font-weight-semibold);
  }

  .archive-list__score {
    color: var(--pulse-color-text-secondary);
    font-size: var(--pulse-font-size-sm);
    font-variant-numeric: tabular-nums;
  }
</style>
```

`packages/site/src/pages/[feed].ts`:

```ts
import rss from "@astrojs/rss";
import type { APIRoute, GetStaticPaths } from "astro";
import { reportPath } from "../lib/report.ts";
import { allReports } from "../lib/reports.ts";
import { getSite } from "../lib/site-data.ts";

const FEED_FILE = "rss.xml";

// A feed needs absolute links, so it exists only when config.site.url is set.
export const getStaticPaths = (() =>
  getSite().location.site === undefined
    ? []
    : [{ params: { feed: FEED_FILE } }]) satisfies GetStaticPaths;

export const GET: APIRoute = async (context) => {
  const { ctx, location } = getSite();
  const site = new URL(location.base, context.site);
  const reports = await allReports();
  return rss({
    title: ctx.t("ui.feed.title"),
    description: ctx.t("ui.site.description"),
    site,
    customData: `<language>${ctx.lang}</language>`,
    items: reports.map((report) => ({
      title: report.headline,
      link: new URL(reportPath(report.meta.date), site).href,
      pubDate: new Date(report.meta.window.end),
      description: report.tldr.map((line) => line.text).join(" "),
    })),
  });
};
```

- [ ] **Step 3: Build and check the output**

Run: `pnpm demo:build && pnpm demo:check`
Expected: 0 check errors and `[pagefind] Pagefind indexed …`, and these files in `examples/dist/`:
- `archive/index.html`
- `rss.xml`
- `sitemap-index.xml`
- `pagefind/`

Run: `grep -c "<item>" examples/dist/rss.xml && grep -o "https://mordris.github.io/PulseAI/2026/10/11/" examples/dist/rss.xml | head -1`
Expected: `3`, then the absolute link to the 2026-10-11 edition.

- [ ] **Step 4: Commit**

```bash
pnpm biome check --write packages/site && pnpm lint
git add packages/site pnpm-lock.yaml
git commit -m "feat(site): add the archive and the RSS feed

The archive shows a calendar heatmap of Pulse scores and every edition by
month. The feed and sitemap are built only when config.site.url gives the
site absolute links.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 15: Browser tests — behaviour, no JavaScript, print, accessibility

**Files:**
- Create: `packages/site/playwright.config.ts`
- Create: `packages/site/scripts/playwright-docker.ts`
- Create: `packages/site/e2e/{support,report.spec,theme.spec,nojs.spec,a11y.spec}.ts`, `packages/site/e2e/fixtures/image.svg`
- Modify: `packages/site/package.json` (scripts, `config.playwrightImage`), root `package.json` (`demo:e2e`)

**Interfaces:**
- Consumes: the built demo (`pnpm demo:build`) and its resolved tokens (`examples/.pulse/tokens/*.json`).
- Produces:
  - Projects `desktop` (light), `desktop-dark` and `mobile` (Pixel 7). The base URL is the instance's own base path (`/PulseAI/` for the demo), served by `pulse-site.ts preview`.
  - `test` with an automatic fixture: requests to other hosts are refused, images get `e2e/fixtures/image.svg`, and uncaught page errors fail the test.
  - Helpers `visualsSettled(page)`, `hexToRgb(hex)`, `tokenValue(mode, path)`.
  - `node scripts/playwright-docker.ts [args]` runs `playwright test` in the image named by `config.playwrightImage`, with the repository mounted at its own path. Only `PULSE_E2E_INSTANCE`, `PULSE_E2E_PORT` and `CI` pass through.
  - Scripts:
    - `e2e`: everything except `@visual`
    - `e2e:visual` and `e2e:visual:update`: Task 16
    - root `demo:e2e`: everything

- [ ] **Step 1: Add Playwright and axe**

Run: `pnpm --filter @pulseai/site add -D @playwright/test @axe-core/playwright`

In `packages/site/package.json`, add to `scripts`:

```json
    "e2e": "node scripts/playwright-docker.ts --grep-invert @visual",
    "e2e:visual": "node scripts/playwright-docker.ts --grep @visual",
    "e2e:visual:update": "node scripts/playwright-docker.ts --grep @visual --update-snapshots"
```

and a top-level `config`. Its tag must equal the installed `@playwright/test` version:

```json
  "config": {
    "playwrightImage": "mcr.microsoft.com/playwright:v1.64.0-noble"
  }
```

Add to the root `package.json` `scripts`:

```json
    "demo:e2e": "pnpm --filter @pulseai/site exec node scripts/playwright-docker.ts"
```

Run: `docker pull mcr.microsoft.com/playwright:v1.64.0-noble`

- [ ] **Step 2: Write the configuration and the helpers**

`packages/site/playwright.config.ts`:

```ts
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";
import { loadSiteContext } from "./src/lib/context.ts";
import { siteLocation, sitePaths } from "./src/lib/setup.ts";

// End-to-end tests run against a built instance (the demo in examples/ unless PULSE_E2E_INSTANCE
// names another), served by `astro preview` at the instance's own base path.
const SITE_DIR = fileURLToPath(new URL(".", import.meta.url));
const INSTANCE = resolve(SITE_DIR, process.env.PULSE_E2E_INSTANCE ?? "../../examples");
const PORT = Number(process.env.PULSE_E2E_PORT ?? 4321);
const { base } = siteLocation(loadSiteContext(sitePaths(INSTANCE).contextFile).config.site.url);
const ORIGIN = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `${ORIGIN}${base}`,
    locale: "en-US",
    timezoneId: "Europe/Istanbul",
    trace: "retain-on-failure",
  },
  expect: {
    toHaveScreenshot: { animations: "disabled", caret: "hide", maxDiffPixelRatio: 0.002 },
  },
  snapshotPathTemplate: "{testDir}/__screenshots__/{projectName}/{arg}{ext}",
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], colorScheme: "light" } },
    { name: "desktop-dark", use: { ...devices["Desktop Chrome"], colorScheme: "dark" } },
    { name: "mobile", use: { ...devices["Pixel 7"], colorScheme: "light" } },
  ],
  webServer: {
    command: `node scripts/pulse-site.ts preview --instance "${INSTANCE}" -- --port ${PORT} --host 127.0.0.1`,
    url: `${ORIGIN}${base}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
```

`packages/site/scripts/playwright-docker.ts`:

```ts
#!/usr/bin/env node
/**
 * Run Playwright inside the pinned Playwright image (package.json config.playwrightImage), so the
 * browsers and fonts match CI and the screenshot baselines.
 *
 *   node scripts/playwright-docker.ts [playwright test arguments]
 *
 * The repository is mounted at its own path with its installed node_modules, which therefore must
 * be built for Linux x64: run this on a Linux host (or in CI). Elsewhere, update screenshots from
 * the CI artifact instead.
 */
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { userInfo } from "node:os";
import { fileURLToPath } from "node:url";

const SITE_DIR = fileURLToPath(new URL("..", import.meta.url));
const REPO_DIR = fileURLToPath(new URL("../../..", import.meta.url));
const PASSED_ENV = ["CI", "PULSE_E2E_INSTANCE", "PULSE_E2E_PORT"];

export function playwrightImage(): string {
  const manifest = JSON.parse(
    readFileSync(new URL("../package.json", import.meta.url), "utf8"),
  ) as {
    config?: { playwrightImage?: string };
  };
  const image = manifest.config?.playwrightImage;
  if (!image) throw new Error("package.json has no config.playwrightImage");
  return image;
}

export function dockerArgs(image: string, testArgs: readonly string[]): string[] {
  const { uid, gid } = userInfo();
  return [
    "run",
    "--rm",
    "--ipc=host",
    `--user=${uid}:${gid}`,
    "--env=HOME=/tmp",
    ...PASSED_ENV.filter((name) => process.env[name] !== undefined).map((name) => `--env=${name}`),
    `--volume=${REPO_DIR}:${REPO_DIR}`,
    `--workdir=${SITE_DIR}`,
    image,
    "npx",
    "playwright",
    "test",
    ...testArgs,
  ];
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const result = spawnSync("docker", dockerArgs(playwrightImage(), process.argv.slice(2)), {
    stdio: "inherit",
  });
  process.exitCode = result.status ?? 1;
}
```

`packages/site/e2e/fixtures/image.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="320" height="160" viewBox="0 0 320 160" role="img">
  <title>Fixture image</title>
  <rect width="320" height="160" fill="gray" />
  <text x="160" y="88" font-family="sans-serif" font-size="20" text-anchor="middle" fill="white">fixture image</text>
</svg>
```

`packages/site/e2e/support.ts`:

```ts
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test as base, expect, type Page } from "@playwright/test";

const IMAGE = readFileSync(fileURLToPath(new URL("./fixtures/image.svg", import.meta.url)));

/**
 * Every test runs offline: requests to other hosts are refused, except images, which get a local
 * fixture so screenshots never depend on a third-party server. Page errors fail the test.
 */
export const test = base.extend<{ pageErrors: string[] }>({
  pageErrors: [
    async ({ page }, use) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.route(
        (url) => url.hostname !== "127.0.0.1" && url.hostname !== "localhost",
        (route) =>
          route.request().resourceType() === "image"
            ? route.fulfill({ status: 200, contentType: "image/svg+xml", body: IMAGE })
            : route.abort(),
      );
      await use(errors);
      expect(errors, "uncaught page errors").toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };

/** Wait until every chart and diagram on the page has rendered or given up. */
export async function visualsSettled(page: Page): Promise<void> {
  await page.waitForFunction(() =>
    [...document.querySelectorAll<HTMLElement>("pulse-vega-chart, pulse-mermaid")].every(
      (element) => element.dataset.state !== undefined,
    ),
  );
}

/** A hex color as getComputedStyle reports it. */
export function hexToRgb(hex: string): string {
  const value = Number.parseInt(hex.slice(1), 16);
  return `rgb(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255})`;
}

const INSTANCE = resolve(
  fileURLToPath(new URL("..", import.meta.url)),
  process.env.PULSE_E2E_INSTANCE ?? "../../examples",
);

/** A token's resolved value in the instance build under test. */
export function tokenValue(mode: "light" | "dark", path: string): string {
  const resolved = JSON.parse(
    readFileSync(join(INSTANCE, ".pulse", "tokens", `${mode}.json`), "utf8"),
  );
  return String(resolved.tokens[path].value);
}
```

- [ ] **Step 3: Write the tests**

`packages/site/e2e/report.spec.ts`:

```ts
import type { Page } from "@playwright/test";
import { expect, test, visualsSettled } from "./support.ts";

const filters = (page: Page) => page.locator("pulse-report-controls");

test.describe("report page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("./");
    await visualsSettled(page);
  });

  test("renders the latest edition with every visual drawn", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Atlas-3 arrives/);
    const states = await page
      .locator("pulse-vega-chart, pulse-mermaid")
      .evaluateAll((elements) => elements.map((element) => (element as HTMLElement).dataset.state));
    expect(states.length).toBeGreaterThan(5);
    expect(states.every((state) => state === "rendered")).toBe(true);
    const sections = await page
      .locator("section.report-section")
      .evaluateAll((elements) => elements.map((e) => e.id));
    expect(sections).toEqual([
      "section-models",
      "section-tooling",
      "section-research",
      "section-oss",
    ]);
  });

  test("opens the item a permalink names", async ({ page }) => {
    await page.goto("./#verify-then-expand");
    await expect(page.locator("details#verify-then-expand")).toHaveAttribute("open", "");
  });

  test("expands and collapses every item", async ({ page }) => {
    await page.getByRole("button", { name: "Expand all" }).click();
    await expect(page.locator("details[data-item]:not([open])")).toHaveCount(0);
    await page.getByRole("button", { name: "Collapse all" }).click();
    await expect(page.locator("details[data-item][open]")).toHaveCount(0);
  });

  test("filters items and hides empty sections", async ({ page }) => {
    await filters(page).getByLabel("Section", { exact: true }).selectOption("oss");
    await expect(page.locator("details[data-item]:visible")).toHaveCount(2);
    await expect(page.locator("#section-models")).toBeHidden();
    await expect(filters(page).getByRole("status")).toHaveText("2 of 14 items shown");
    await filters(page).getByLabel("Section", { exact: true }).selectOption("all");
    await filters(page).getByLabel("New or update", { exact: true }).selectOption("updates");
    await expect(page.locator("details[data-item]:visible")).toHaveCount(1);
    await filters(page).getByLabel("Impact", { exact: true }).selectOption("5");
    await filters(page).getByLabel("New or update", { exact: true }).selectOption("all");
    await expect(page.locator("details[data-item]:visible")).toHaveCount(3);
    await page.getByRole("button", { name: "Reset" }).click();
    await expect(page.locator("details[data-item]:visible")).toHaveCount(14);
  });

  test("says so when no item matches", async ({ page }) => {
    await filters(page).getByLabel("Section", { exact: true }).selectOption("oss");
    await filters(page).getByLabel("New or update", { exact: true }).selectOption("updates");
    await expect(filters(page).getByRole("status")).toHaveText("No items match these filters.");
  });

  test("a broken chart keeps its table and does not stop other charts", async ({ page }) => {
    await page.evaluate(() => {
      const figure = document.createElement("figure");
      figure.id = "visual-broken";
      figure.innerHTML = `<pulse-vega-chart><script type="application/json">{"mark":"nope","data":{"values":[{"a":1}]}}</script><div data-chart hidden></div></pulse-vega-chart><details data-chart-table open><summary>data</summary></details>`;
      document.querySelector("main")?.append(figure);
    });
    const broken = page.locator("#visual-broken pulse-vega-chart");
    await expect(broken).toHaveAttribute("data-state", "error");
    await expect(page.locator("#visual-broken details[data-chart-table]")).toHaveAttribute(
      "open",
      "",
    );
    await expect(page.locator("pulse-vega-chart[data-state=rendered]").first()).toBeVisible();
  });

  test("a broken diagram keeps its alt text and source", async ({ page }) => {
    await page.evaluate(() => {
      const figure = document.createElement("figure");
      figure.id = "visual-broken-diagram";
      figure.innerHTML = `<pulse-mermaid><div data-diagram hidden></div><p data-diagram-fallback>alt text</p></pulse-mermaid><details data-diagram-source><summary>source</summary><pre><code>flowchart LR\n  A --></code></pre></details>`;
      document.querySelector("main")?.append(figure);
    });
    await expect(page.locator("#visual-broken-diagram pulse-mermaid")).toHaveAttribute(
      "data-state",
      "error",
    );
    await expect(page.getByText("alt text")).toBeVisible();
  });
});

test.describe("other routes", () => {
  test("serves every edition at its date and lists them in the archive", async ({ page }) => {
    await page.goto("archive/");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Archive");
    await expect(page.locator(".archive-list li")).toHaveCount(3);
    await page.getByRole("link", { name: /Relay CLI 3.0 enters release candidate/ }).click();
    await expect(page).toHaveURL(/\/2026\/10\/10\/$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Relay CLI 3.0 enters/);
  });

  test("points the front page at the edition it repeats", async ({ page }) => {
    await page.goto("./");
    await expect(page.locator("link[rel=canonical]")).toHaveAttribute(
      "href",
      /\/PulseAI\/2026\/10\/11\/$/,
    );
  });

  test("answers unknown pages with the not-found page", async ({ page }) => {
    const response = await page.goto("no-such-page/");
    expect(response?.status()).toBe(404);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Page not found");
  });

  test("publishes a feed with absolute links below the base path", async ({ request }) => {
    const response = await request.get("rss.xml");
    expect(response.ok()).toBe(true);
    const feed = await response.text();
    expect(feed.match(/<item>/g)).toHaveLength(3);
    expect(feed).toContain("<link>https://mordris.github.io/PulseAI/2026/10/11/</link>");
  });

  test("finds editions with search, without duplicating the front page", async ({ page }) => {
    await page.goto("archive/");
    await page.getByRole("combobox").fill("Atlas");
    const results = page.locator("pagefind-searchbox a[href*='/2026/']");
    await expect(results.first()).toBeVisible();
    const links = await page
      .locator("pagefind-searchbox a")
      .evaluateAll((anchors) => anchors.map((anchor) => anchor.getAttribute("href")));
    expect(links).not.toContain("/PulseAI/");
  });
});
```

`packages/site/e2e/theme.spec.ts`:

```ts
import { expect, hexToRgb, test, tokenValue, visualsSettled } from "./support.ts";

const background = (page: import("@playwright/test").Page) =>
  page.evaluate(() => getComputedStyle(document.body).backgroundColor);

test.describe("theme", () => {
  test("follows the OS until the reader picks a theme", async ({ page }, testInfo) => {
    const mode = testInfo.project.use.colorScheme === "dark" ? "dark" : "light";
    await page.goto("./");
    expect(await background(page)).toBe(hexToRgb(tokenValue(mode, "color.surface.page")));
    await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.*/);
  });

  test("remembers the reader's pick across pages", async ({ page }) => {
    await page.goto("./");
    await page.getByRole("radio", { name: "Dark" }).check();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.goto("archive/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect(await background(page)).toBe(hexToRgb(tokenValue("dark", "color.surface.page")));
    await page.getByRole("radio", { name: "Auto" }).check();
    await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.*/);
  });

  test("honours a valid theme query and ignores an invalid one", async ({ page }) => {
    await page.goto("./?theme=light");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await page.goto("./?theme=neon");
    await expect(page.locator("html")).toHaveAttribute("data-theme-choice", "auto");
  });

  test("survives storage that throws", async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(window, "localStorage", {
        get() {
          throw new DOMException("blocked", "SecurityError");
        },
      });
    });
    await page.goto("./");
    await page.getByRole("radio", { name: "Dark" }).check();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  });

  test("re-themes charts when the theme changes", async ({ page }) => {
    await page.goto("./?theme=light");
    await visualsSettled(page);
    const label = page.locator("#visual-impact-by-section pulse-vega-chart svg text").first();
    const light = await label.getAttribute("fill");
    expect(light).toBe(tokenValue("light", "color.chart.label"));
    await page.getByRole("radio", { name: "Dark" }).check();
    await expect(label).toHaveAttribute("fill", tokenValue("dark", "color.chart.label"));
  });
});
```

`packages/site/e2e/nojs.spec.ts`:

```ts
import { expect, test } from "./support.ts";

test.use({ javaScriptEnabled: false });

test.describe("without JavaScript", () => {
  test("every item is reachable and every chart shows its data", async ({ page }) => {
    await page.goto("./");
    await expect(page.locator("details[data-item]")).toHaveCount(14);
    await expect(page.locator("details[data-chart-table][open]").first()).toBeAttached();
    expect(await page.locator("details[data-chart-table]:not([open])").count()).toBe(0);
    await expect(page.locator("pulse-report-controls")).toBeHidden();
    await expect(page.locator("pulse-theme-switch")).toBeHidden();
    await page.locator("details#verify-then-expand > summary").click();
    await expect(page.locator("details#verify-then-expand [data-diagram-fallback]")).toBeVisible();
  });
});

test.describe("print", () => {
  test("expands every item", async ({ page }) => {
    await page.goto("./");
    await page.emulateMedia({ media: "print" });
    await expect(page.locator("details#northwind-atlas-3 .item__note--why")).toBeVisible();
    await expect(page.locator("pulse-report-controls")).toBeHidden();
  });
});
```

`packages/site/e2e/a11y.spec.ts`:

```ts
import AxeBuilder from "@axe-core/playwright";
import { expect, test, visualsSettled } from "./support.ts";

const IMPACTS = new Set(["serious", "critical"]);

for (const path of ["./", "archive/", "2026/10/09/"]) {
  test(`no serious accessibility problems on ${path}`, async ({ page }) => {
    await page.goto(path);
    await visualsSettled(page);
    // Audit the expanded deep dives too, not only the summaries.
    await page.evaluate(() => {
      for (const details of document.querySelectorAll("details")) details.open = true;
    });
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
      .analyze();
    const problems = results.violations
      .filter(
        (violation) =>
          violation.impact !== undefined &&
          violation.impact !== null &&
          IMPACTS.has(violation.impact),
      )
      .map(
        (violation) =>
          `${violation.id}: ${violation.nodes.map((node) => node.target.join(" ")).join(", ")}`,
      );
    expect(problems).toEqual([]);
  });
}
```

- [ ] **Step 4: Run them**

Run: `pnpm demo:build && pnpm --filter @pulseai/site e2e`
Expected: `66 passed`, 22 tests in each of the three projects. That includes:
- the axe audits (no serious or critical violations, with every `details` open);
- the injected broken chart and broken diagram cases;
- the theme cases (storage that throws, an invalid `?theme=`, charts re-themed on a switch).

A failure here is a bug in the site, not the test: read the trace in `packages/site/test-results/` and fix the component.

- [ ] **Step 5: Commit**

```bash
pnpm biome check --write packages/site package.json && pnpm lint
git add packages/site package.json pnpm-lock.yaml
git commit -m "test(site): add Playwright and axe tests in the Playwright container

Covers rendering, permalinks, filters, expand and collapse, broken charts
and diagrams, theme persistence and overrides, the no-JavaScript and print
views, the archive, the feed, search, and axe audits in light, dark, and
mobile.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 16: Screenshot tests

**Files:**
- Create: `packages/site/e2e/visual.spec.ts`
- Create (generated): `packages/site/e2e/__screenshots__/{desktop,desktop-dark,mobile}/*.png`

**Interfaces:**
- Consumes: Task 15's configuration (`snapshotPathTemplate`, `toHaveScreenshot` defaults with `maxDiffPixelRatio: 0.002`, animations disabled) and helpers.
- Produces:
  - Baselines for each project: `latest.png` (full page), `archive.png` (full page), `item-<id>.png` for the expanded Atlas-3, verify-then-expand and pyfetchkit items, and `item-long-title.png`. The last is the Quillmark brief, whose long title must wrap on mobile without overflow.
  - All are tagged `@visual` and always produced inside the Playwright container, so fonts and rendering match CI.

- [ ] **Step 1: Write the test**

`packages/site/e2e/visual.spec.ts`:

```ts
import type { Page } from "@playwright/test";
import { expect, test, visualsSettled } from "./support.ts";

/** A page ready for a screenshot: fonts loaded, every chart and diagram drawn. */
async function settle(page: Page): Promise<void> {
  await visualsSettled(page);
  await page.evaluate(() => document.fonts.ready);
}

test.describe("screenshots @visual", () => {
  test("latest edition", async ({ page }) => {
    await page.goto("./");
    await settle(page);
    await expect(page).toHaveScreenshot("latest.png", { fullPage: true });
  });

  test("deep dives", async ({ page }) => {
    for (const id of ["northwind-atlas-3", "verify-then-expand", "pyfetchkit-path-traversal"]) {
      await page.goto(`./#${id}`);
      await settle(page);
      await expect(page.locator(`details#${id}`)).toHaveScreenshot(`item-${id}.png`);
    }
  });

  test("long title brief", async ({ page }) => {
    await page.goto("./#quillmark-1-8-4");
    await settle(page);
    await expect(page.locator("details#quillmark-1-8-4")).toHaveScreenshot("item-long-title.png");
  });

  test("archive", async ({ page }) => {
    await page.goto("archive/");
    await settle(page);
    await expect(page).toHaveScreenshot("archive.png", { fullPage: true });
  });
});
```

- [ ] **Step 2: Create the baselines and review them**

Run: `pnpm demo:build && pnpm --filter @pulseai/site e2e:visual:update`
Expected: 18 PNG files under `packages/site/e2e/__screenshots__/`.

Open each image and check it against the spec before committing:
- **Light and dark:** both themes are readable.
- **Layout:** nothing overflows on mobile, and the long title wraps.
- **Visuals:** charts are drawn, not left as tables.
- **Code:** `>=` stays two characters (code turns ligatures off).

A baseline that shows a defect must not be committed: fix the site and regenerate.

- [ ] **Step 3: Check that they are stable**

Run: `pnpm --filter @pulseai/site e2e:visual`
Expected: `12 passed` with no differences, the second run matching the first exactly.

- [ ] **Step 4: Commit**

```bash
pnpm biome check --write packages/site && pnpm lint
git add packages/site/e2e
git commit -m "test(site): add screenshot baselines for light, dark, and mobile

Full pages for the latest edition and the archive, plus expanded deep
dives and the long-title brief, rendered in the pinned Playwright image.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 17: CI, repository settings, dependency automation, and documentation

**Files:**
- Modify: `.github/workflows/ci.yml` (new `site` job), `.github/repository.yml` (required check)
- Modify: `renovate.json`, `release-please-config.json`, `.release-please-manifest.json`
- Create: `docs/site.md`, `docs/adr/0002-site-rendering.md`
- Modify: `README.md`, `CONTRIBUTING.md`

**Interfaces:**
- Consumes: every earlier task's scripts: `tokens:check`, `demo:build`, `demo:check`, `demo:e2e`, and `pulse tokens check`.
- Produces:
  - A `site` CI job, the same hardening as every job, which runs in order:
    1. the token gate for every preset
    2. the demo build
    3. the demo's token check
    4. `astro check`
    5. all Playwright tests in the pinned image
    It uploads `playwright-report` on failure.
  - `site` among the ruleset's required checks.
  - Renovate keeps `@playwright/test` and the image in one group and the site's TypeScript below 7.
  - release-please versions `tokens` and `site` together with `cli` and `contracts`.
- The node job's `pnpm typecheck` and `pnpm test` already cover the site's `tsc` and Vitest tests, which need no build.

- [ ] **Step 1: Add the CI job**

Append to `.github/workflows/ci.yml`, after the `node` job:

```yaml
  site:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: step-security/harden-runner@ccd8616d44fd3846e67624a50d5aad6d37bf2d25 # v2.22.1
        with:
          egress-policy: audit
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884 # v10.3.0
        with:
          python-version: "3.12"
          enable-cache: true
      - uses: pnpm/action-setup@ea17c68df8912ef543352723c149a84f56e3d413 # v6.1.0
      - uses: actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0
        with:
          node-version: lts/*
          cache: pnpm
      - run: uv sync --locked
      - run: pnpm install --frozen-lockfile
      - name: Gate every engine theme preset
        run: pnpm tokens:check
      - name: Build the demo instance
        run: pnpm demo:build
      - name: Gate the demo instance's tokens
        run: uv run pulse tokens check --instance examples
      - name: Type-check the site
        run: pnpm demo:check
      # Functional, accessibility, and screenshot tests, in the pinned Playwright image.
      - name: End-to-end tests
        run: pnpm demo:e2e
      - if: failure()
        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with:
          name: playwright-report
          path: |
            packages/site/playwright-report
            packages/site/test-results
          retention-days: 14
```

Run: `uvx zizmor .github/workflows/`
Expected: `No findings to report.`

- [ ] **Step 2: Require the check**

In `.github/repository.yml`, add `- site` to `ruleset.required_checks`, after `- node`.

Run: `uv run pytest packages/cli/tests/test_repo_settings.py -q`
Expected: PASS. The ruleset body now lists `site`.

The setting reaches GitHub only when `scripts/github/apply_repo_settings.py` runs. **Do not run it from the task.** Requiring a check before the first PR has produced it would block every PR. After this branch's PR shows a green `site` check, ask the repository owner to approve, then run `uv run python scripts/github/apply_repo_settings.py`.

- [ ] **Step 3: Teach Renovate about the site**

Add to `renovate.json`:

```json
{
  "customManagers": [
    {
      "customType": "regex",
      "description": "The Playwright image the site's browser tests run in (packages/site/package.json config.playwrightImage)",
      "managerFilePatterns": ["/^packages/site/package\\.json$/"],
      "matchStrings": [
        "\"playwrightImage\": \"(?<depName>mcr\\.microsoft\\.com/playwright):(?<currentValue>v[^\"]+)\""
      ],
      "datasourceTemplate": "docker"
    }
  ]
}
```

and append these entries to `packageRules`:

```json
[
  {
    "description": "The Playwright image must carry the same version as @playwright/test; screenshots may need updating",
    "groupName": "playwright",
    "matchPackageNames": ["@playwright/test", "mcr.microsoft.com/playwright"],
    "automerge": false
  },
  {
    "description": "@astrojs/check supports TypeScript 5 and 6 only; the rest of the repository uses 7",
    "matchFileNames": ["packages/site/package.json"],
    "matchPackageNames": ["typescript"],
    "allowedVersions": "<7"
  }
]
```

Run: `npx --yes --package renovate -- renovate-config-validator renovate.json`
Expected: `Config validated successfully`.

- [ ] **Step 4: Version the new packages**

In `release-please-config.json`:
- set the `linked-versions` plugin's `components` to `["cli", "contracts", "tokens", "site"]`;
- add these entries to `packages`:

```json
    "packages/tokens": { "release-type": "node", "package-name": "@pulseai/tokens", "component": "tokens" },
    "packages/site": { "release-type": "node", "package-name": "@pulseai/site", "component": "site" }
```

In `.release-please-manifest.json`, add `"packages/tokens": "0.1.0"` and `"packages/site": "0.1.0"`.

- [ ] **Step 5: Write the documentation**

`docs/site.md`:

````markdown
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
````

`docs/adr/0002-site-rendering.md`:

````markdown
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
````

In `README.md`, make these changes:

1. Before the `<details>` block "Install the Claude Code plugin", insert:

````markdown
### Build the demo site

`examples/` is a demo instance with three sample editions:

```bash
pnpm demo:build      # site context, design tokens, and the site in examples/dist/
pnpm demo:preview    # http://127.0.0.1:4321/PulseAI/
pnpm demo:e2e        # Playwright, axe, and screenshot tests (Docker)
```

See [docs/site.md](docs/site.md) for themes, presets, item types, and visuals.
````

2. In the repository layout, replace the `locales/` … `packages/contracts/` lines with:

```text
locales/               interface text
tokens/                design tokens (DTCG): base, modes, and theme presets
examples/              demo instance with sample reports
packages/cli/          the pulse CLI (Python, uv)
packages/contracts/    Zod validators and types built from the schemas (TypeScript)
packages/tokens/       token layering and resolution (Style Dictionary)
packages/site/         the report site (Astro)
```

3. In the concerns table, set these rows:
   - Report site: built on `Astro, Pagefind, Style Dictionary, Fontsource`, status `Available`.
   - Charts and diagrams: status `Available`.
   - Browser automation and QA: built on `Playwright, axe-core, ColorAide`, status `Available (design review agent: M4)`.

4. In the roadmap, mark M1 and M2 as `Done`.

In `CONTRIBUTING.md`, make these changes:

1. After the everyday commands block, add:

```text
The report site (see [docs/site.md](docs/site.md)):

    pnpm demo:build                                 # build the demo instance in examples/
    pnpm demo:dev                                   # live reload while editing components
    pnpm demo:check                                 # astro check
    pnpm tokens:check                               # contrast and color gates for every preset
    pnpm demo:e2e                                   # Playwright, axe, screenshots (Docker)
    pnpm --filter @pulseai/site e2e:visual:update   # accept intended visual changes (Linux)
    pnpm --filter @pulseai/contracts generate       # after editing schema/*.schema.json
```

2. Extend the "values live in registries" rule to name `tokens/`, and say that the site's copy comes from locales and its colors, fonts and sizes from tokens.

3. In "Releasing", say that the release tags `cli`, `contracts`, `tokens` and `site` together, and that the npm packages stay private until M6 builds and publishes them.

- [ ] **Step 6: Run everything CI runs**

Run:

```bash
uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest -q
uv run python scripts/generate_models.py --check
pnpm lint && pnpm typecheck && pnpm test
pnpm tokens:check && pnpm demo:build && uv run pulse tokens check --instance examples && pnpm demo:check && pnpm demo:e2e
```

Expected:
- every Python test passes, and the models are current;
- lint, types and the TypeScript tests pass in `@pulseai/contracts`, `@pulseai/tokens` and `@pulseai/site`;
- the three presets and the demo pass the token gate;
- `astro check` reports 0 errors;
- Playwright reports `78 passed`.

- [ ] **Step 7: Commit**

```bash
pnpm biome check --write . && pnpm lint
git add .github renovate.json release-please-config.json .release-please-manifest.json docs README.md CONTRIBUTING.md
git commit -m "ci(site): build, gate, and test the site on every pull request

The site job gates every theme preset, builds the demo instance, runs astro
check, and runs the Playwright, axe, and screenshot tests in the pinned
image. Renovate moves Playwright and its image together; release-please
versions the tokens and site packages with the engine. Adds docs/site.md
and ADR 0002.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
