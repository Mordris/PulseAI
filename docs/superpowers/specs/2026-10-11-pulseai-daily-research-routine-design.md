# PulseAI — Daily AI & Software Research Routine — Design Spec

- **Date:** 2026-10-11
- **Version:** 2 (v1 replaced: OSS-first, registry-driven, production-grade stack)
- **Status:** Draft for review
- **Owner:** @Mordris

## 1. Purpose

Staying current in AI and software is hard: models, agent tooling, papers, and open source move daily. PulseAI is a Claude Code–driven routine that, once per day, researches what changed, verifies it against primary sources, compares it to what it already reported, and publishes **one** heavily visualized, consistently designed report, then notifies the reader.

It is a **public GitHub project** so anyone can run their own instance in ~15 minutes. Daily reports are private to each instance; the public repo ships only a few example reports.

### Success criteria

1. One report per day arrives at the configured time (default start **17:00 Europe/Istanbul**), on any of three hosts.
2. The reader never misses a major model release, tool release, notable paper, or important OSS/security event in the configured interest area.
3. Every item is traceable to a primary source fetched during the run; every number in a chart traces to a quoted source span.
4. Every report has the same recognizable structure and design system, while visuals are generated per item and pass automated design and accessibility checks in light, dark, and mobile.
5. A stranger can go from zero to first report in ≤15 minutes using the docs and `pulse doctor`.
6. Adding a section, item type, source, language, or theme requires **no code change** — only registry/config files.

### Non-goals (v1)

- AI-generated images (decided: **real images only**; charts/diagrams/GIFs remain generative).
- Multi-user accounts, comments, or a hosted SaaS.
- Weekly/monthly editions (archive + story threads make them easy later).
- Real-time alerts during the day.

## 2. Decisions log

| # | Decision |
|---|---|
| D1 | Support **three hosts** via thin adapters over one core: Claude Code cloud **routine**, **GitHub Actions** (`claude-code-action@v1`), **local** (systemd/launchd + `claude -p`). |
| D2 | Reports stored in a **private repo** with a static site. |
| D3 | Default coverage: **Models & labs**, **Agentic dev tooling**, **Research desk** (papers + articles), **Software & OSS** (incl. security) — defined in a registry, not code. |
| D4 | Notifications are **pluggable** via **Apprise** (Telegram, email, Slack, Discord, ntfy, …). |
| D5 | Language **configurable**, default English; UI strings in locale files. |
| D6 | **Claude drives the whole run** (search/collect → curate → compare with history → write → design → publish → notify). Scripts and MCP servers are tools Claude calls. |
| D7 | Schedule **configurable**; default start 17:00 Europe/Istanbul. |
| D8 | **Fixed frame + generative visuals**: frame and design tokens are locked; Claude designs per-item charts, dashboards, diagrams, motion and uses real images — constrained by a design skill and enforced by automated gates. |
| D9 | Every item expands into a **type-specific deep-dive** with visualizations. |
| D10 | **Dark/light theme switch** (Auto/Light/Dark), configurable presets and overrides. |
| D11 | Research desk with full-text **paper understanding** and long-form **articles**; academic sources beyond arXiv. |
| D12 | Default interests profile: **agents + Claude Code + MCP** (plus general frontier AI). |
| D13 | **Two repos**: public engine `PulseAI` + private `pulse-instance` per user. Private viewing via **Cloudflare Pages + Cloudflare Access**; GitHub Pages optional for public instances. |
| D14 | **OSS over custom code.** Use maintained open-source projects for every concern that has one; custom code is limited to thin glue. |
| D15 | **Latest versions, locked and auto-updated**: start every dependency at its latest stable release; lockfiles for reproducibility; **Renovate** keeps them current through CI-gated PRs. |
| D16 | **Nothing hardcoded**: sections, item types, sources, locales, design tokens, models, thresholds, limits, prompts live in schema-validated registries/config. |
| D17 | **Rendering stack: Astro** (content collections + per-type components + Pagefind + Style Dictionary tokens + Vega-Lite/Mermaid). |
| D18 | **Data access: MCP-first + one generic registry-driven collector** for RSS/Atom/JSON APIs; zero per-source code. |
| D19 | **Production grade**: typed code, CI quality gates, semantic releases, published packages, security scanning, observability. |

## 3. Engineering standards (apply to every component)

### 3.1 OSS-first rule
Before writing code for a concern, use an actively maintained OSS project (recent commits, permissive license, real adoption). Custom code is allowed only as glue between OSS components or where no suitable project exists — and must then be generic (driven by registry/config), not source- or type-specific.

### 3.2 Versions policy
- Every dependency starts at its **latest stable** version at implementation time (Python, Node, npm, PyPI, MCP servers, GitHub Actions, CDN-free vendored assets).
- **Lockfiles are mandatory**: `uv.lock`, `pnpm-lock.yaml`; GitHub Actions pinned by commit SHA.
- **Renovate** (config in both repos) opens update PRs for all ecosystems; CI must pass; patch/minor auto-merge, majors need review. Instances get the same config, including engine version bumps.
- Runtime floors are declared, not assumed: Python ≥3.12 (latest stable in CI), Node current LTS, Claude Code ≥ the version required by used flags (checked by `pulse doctor`).

### 3.3 No-hardcoding rule
Code may not embed: section ids or labels, item-type lists, source URLs, model ids, colors, fonts, copy/UI strings, thresholds, limits, schedules, or prompts. These come from:

| Kind | Location (engine default, overridable per instance) |
|---|---|
| Data contracts | `schema/*.schema.json` (JSON Schema 2020-12) — **single source of truth** |
| Sections | `taxonomy/sections.yaml` |
| Item types | `taxonomy/item-types.yaml` + `schema/item-types/<type>.schema.json` + site component |
| Sources | `sources/registry/*.yaml` |
| UI strings | `locales/<lang>.json` |
| Design tokens | `tokens/**/*.json` (W3C Design Tokens format) |
| Behavior | `pulse.config.yaml` (schema: `schema/config.schema.json`) |
| Agent behavior | skills/agents Markdown in the plugin |

Instance overrides use the same paths inside `pulse-instance` (deep-merged; instance wins).

### 3.4 Production-grade checklist
- Typed: Pyright (strict) for Python, TypeScript strict for the site.
- Lint/format: Ruff (Python), Biome (TS/JSON/CSS).
- Tests: pytest, Vitest, Playwright (E2E + visual regression), axe-core accessibility audits, agent evals.
- CI on every PR; required checks; pre-commit hooks.
- Releases: **release-please** (monorepo manifest) → semver tags, changelogs, publish `pulseai` (PyPI), `@pulseai/site` (npm), plugin marketplace version.
- Security: CodeQL, dependency review, secret scanning, least-privilege workflow permissions, SHA-pinned actions.
- Observability: structured JSON logs (structlog), run metrics file, Claude Code **OpenTelemetry** export (optional endpoint), System health page.
- Docs: quickstarts per host, registry authoring guides, architecture overview, ADRs for major decisions.

## 4. Architecture overview

```
                    ┌──────────── Host adapter (one of) ─────────────┐
                    │ Cloud routine │ GitHub Actions │ systemd/launchd│
                    └──────────────┬─────────────────────────────────┘
                                   │ runs `/pulse:daily` in a clone of pulse-instance
                                   ▼
┌──────────────────────── Editor-in-chief (main session) ─────────────────────────────┐
│ 1 Load memory → 2 Parallel research → 3 History check → 4 Verify → 5 Write          │
│ → 6 Build site + design/a11y review → 7 Publish → 8 Notify                          │
│                                                                                     │
│ Subagents (registry-configured models): section researchers · paper-triage ·        │
│   paper-analyst · verifier · design-reviewer                                        │
│ Tools: MCP servers (GitHub, Hugging Face, arXiv, fetch, Exa/Brave, Playwright) ·    │
│        WebSearch/WebFetch · `pulse` CLI (collect, validate, history, publish, notify)│
└─────────────────────────────────────────────────────────────────────────────────────┘
                                   │ git push (report.json + assets + state)
                                   ▼
     pulse-instance (private) ──▶ Cloudflare Pages builds Astro site (@pulseai/site) ──▶ Access-protected URL
                                   │
                                   ▼
                       Apprise → Telegram / email / Slack / Discord / ntfy
```

**Principle:** the model produces *schema-validated data and constrained visual specs*; OSS renderers (Astro components, Vega-Lite, Mermaid) produce the frame. Freedom where it adds value (coverage, explanation, visualization), determinism where consistency matters (structure, tokens, theming, validation).

## 5. OSS component map

Versions are the latest stable as of 2026-10-11 and are the starting pins; Renovate moves them forward.

| Concern | Component | Version | Role |
|---|---|---|---|
| Site framework | Astro | 7.3.8 | Static site, content collections (schema-validated `report.json`), per-type components, i18n routing |
| Schema in TS | Zod | 4.6.5 | `z.fromJSONSchema()` builds collection schemas straight from `schema/*.json` |
| Search | Pagefind (+ astro-pagefind) | 1.5.2 (+2.0.1) | Static full-text search |
| Design tokens | Style Dictionary | 5.6.1 | DTCG tokens → CSS variables (light/dark), chart themes (JSON), TS constants |
| Charts | Vega / Vega-Lite / vega-embed | 6.4.0 / 6.5.0 / 7.3.0 | Generative charts; static SVG/PNG via `vl-convert-python` 1.9.0 |
| Diagrams | Mermaid (+ astro-mermaid) | 12.1.0 (+2.1.0) | Method/architecture diagrams |
| Browser automation | Playwright, Playwright MCP | 1.64.0, 0.0.83 | Screenshots, E2E, visual regression, design-reviewer vision input |
| Accessibility | axe-core + @axe-core/playwright | 4.14.0 + 4.13.0 | Contrast and a11y audits on rendered pages |
| Palette distances | ColorAide | 8.13 | OKLab ΔE + CVD simulation for token validation |
| Single-file export | single-file-cli | 2.18.1 | Self-contained offline/email HTML of each report |
| GIF | gifski | latest | Motion captures |
| Feeds | feedparser | 6.0.14 | RSS/Atom parsing in the generic collector |
| HTTP | httpx + hishel + tenacity | 0.28.1 + 1.4.0 + 9.2.1 | Requests, HTTP caching, retries |
| Field mapping | jmespath | 1.1.0 | Registry-declared JSON → candidate mapping |
| URLs / slugs | courlan / python-slugify | 1.4.0 / 9.1.3 | URL normalization, ASCII ids |
| HTML sanitizing | nh3 | 0.3.7 | Sanitize any HTML from sources before storage |
| Research APIs | openreview-py, pyalex, semanticscholar, arxiv | 2.8.0, 0.21, 0.12.0, 4.0.1 | Venue/citation/enrichment data (where MCP lacks coverage) |
| Python models | datamodel-code-generator | 0.83.0 | Pydantic models generated from `schema/*.json` (CI checks drift) |
| Validation CLI | check-jsonschema | 0.38.2 | Validate config/registries/reports in CI and runs |
| Python CLI | Typer, Pydantic, pydantic-settings, structlog | 0.27.3, 2.14.0, 2.15.0, 26.1.0 | Glue CLI, config + env overrides, JSON logs |
| Notifications | Apprise | 2.0.1 | All notification channels |
| MCP servers | github/github-mcp-server, huggingface/hf-mcp-server, blazickjp/arxiv-mcp-server (0.8.2), mcp-server-fetch (2026.10.10), exa-labs/exa-mcp-server, brave/brave-search-mcp-server, microsoft/playwright-mcp | latest | Data access and browsing |
| Tooling | uv, pnpm, Ruff, Pyright, Biome, Vitest, TypeScript, pre-commit | latest (uv 0.11.x, pnpm 12.11.2, Ruff 0.17.0, Pyright 1.1.414, Biome 2.5.15, Vitest 5.0.3, TS 7.0.2, pre-commit 4.6.2) | Build, lint, type, test |
| Release & deps | release-please, Renovate | latest | Versioning, changelogs, dependency freshness |
| Claude integration | Claude Code plugin + marketplace, claude-code-action@v1 | latest | Skills, agents, hooks; Actions host |

## 6. Repositories

### 6.1 `PulseAI` (public engine, monorepo)

```
.claude-plugin/marketplace.json
plugins/pulse/
  .claude-plugin/plugin.json
  skills/  daily/ pulse-design/ paper-brief/ source-vetting/      # Markdown + references
  agents/  section-researcher.md paper-triage.md paper-analyst.md verifier.md design-reviewer.md
  hooks/hooks.json                                                 # guardrails (§13)
  mcp/servers.yaml                                                 # MCP server catalog → generated .mcp.json
schema/                       # JSON Schema 2020-12 — single source of truth
  config.schema.json  report.schema.json  item.schema.json  visual.schema.json
  section.schema.json  source.schema.json  candidate.schema.json  coverage.schema.json  run.schema.json
  item-types/<type>.schema.json
taxonomy/  sections.yaml  item-types.yaml
sources/registry/*.yaml       # default source registry, grouped by domain
locales/<lang>.json           # en, tr to start
tokens/                       # DTCG: base/, themes/<preset>/{light,dark}.json
packages/
  cli/   (Python, uv) → PyPI `pulseai`, command `pulse`
    collect/ (generic collector) validate/ history/ publish/ notify/ schedule/ doctor/ registry/ (loader + merge)
    models/ (generated from schema/)
  site/  (Astro, pnpm) → npm `@pulseai/site`
    components/frame/  components/items/<Type>.astro  components/visuals/{VegaLite,Mermaid,DataTable,Figure,Dashboard}.astro
    content.config.ts (collections from JSON Schema)  pages/  styles/ (generated tokens)
templates/instance/           # skeleton for `pulse init` / "Use this template"
adapters/  routine/  github-actions/  local/
examples/                     # 2–3 real example reports + public demo site
docs/                         # quickstarts, registry guides, ADRs
.github/workflows/  renovate.json  release-please-config.json  .pre-commit-config.yaml
```

### 6.2 `pulse-instance` (private, per user)

```
pulse.config.yaml
taxonomy/ sources/ locales/ tokens/   # optional overrides, same shape as engine
package.json  pnpm-lock.yaml          # depends on @pulseai/site@<version> (Cloudflare Pages builds it)
.claude/settings.json                 # marketplace + enabledPlugins (pulse@pulseai)
.mcp.json                             # generated by `pulse mcp sync` from the server catalog + config
.github/workflows/daily.yml           # only for the Actions host
renovate.json
reports/YYYY/MM/DD/{report.json, report.md, report.single.html, assets/}
state/{coverage.jsonl, threads.jsonl, last_run.json, lock.json, snapshots/}
runs/YYYY-MM-DD/                      # checkpoints; run.json kept, rest git-ignored
```

The engine is consumed as: plugin (marketplace), CLI (`uvx pulseai@<version>` or `uv tool install`), site package (`@pulseai/site@<version>`). One `engine.version` in config; `pulse doctor` checks the three agree.

## 7. Registries and configuration

### 7.1 `pulse.config.yaml` (validated by `schema/config.schema.json`; env overrides via `PULSE__…`)

```yaml
engine: { version: "1.0.0" }
schedule: { time: "17:00", tz: "Europe/Istanbul", cloud_offset_minutes_when_on_hour: 7 }
language: en
interests:
  high: [claude code, agentic coding, mcp, skills, plugins, agent frameworks, llm reasoning, evals]
  normal: [frontier models, open-weights models, inference, ai security]
sections:                       # enable/limit sections defined in taxonomy/sections.yaml
  models:   { enabled: true, max_items: 8 }
  tooling:  { enabled: true, max_items: 10 }
  research: { enabled: true, max_items: 20, options: { max_papers_deep: 6, max_long_reads: 4 } }
  oss:      { enabled: true, max_items: 8 }
deep_dive: { min_impact: 3 }
confidence: { reported: signals_box, rumor: exclude }
window: { max_hours: 72 }
models_by_role:                 # role names come from the plugin's agents
  editor: claude-opus-5-5
  paper-analyst: claude-opus-5-5
  verifier: claude-opus-5-5
  section-researcher: claude-sonnet-5-5
  paper-triage: claude-haiku-5-5
  design-reviewer: claude-sonnet-5-5
limits: { run_minutes: 45, max_budget_usd: 15, design_fix_rounds: 2, agent_max_turns: 60 }
quality:                        # thresholds (no thresholds in code)
  text_contrast_min: 4.5
  section_delta_e_min: 12
  section_cvd_fail: 6
  section_cvd_target: 8
  design_review_min_score: 7
  primary_tiers: [T1, T1-data]   # source tiers that count as primary evidence for confirmed items
theme: { default: auto, switcher: true, preset: pulse, overrides: {} }
visuals: { min_per_deep_dive: 1, motion: true, notify_media: png }
mcp:                            # which catalog servers to enable; keys via env/secrets
  enabled: [github, huggingface, arxiv, fetch, playwright]
  optional: [exa, brave]
site: { url: "https://pulse.example.com", search: true }
publish: { repo: "<owner>/pulse-instance", branch: main }
notify: { urls_env: PULSE_NOTIFY_URLS, on_failure: true }
telemetry: { otel_endpoint_env: OTEL_EXPORTER_OTLP_ENDPOINT }
```

### 7.2 `taxonomy/sections.yaml`

Each section: `id`, `label` (locale key), `color_token`, `order`, `rubric` (impact 1–5 definitions), `default_item_types`, `researcher_brief` (Markdown file path given to the section researcher), `groups` (optional sub-groups, e.g. research desk: paper-of-the-day, top papers, also notable, long reads, venue watch — each a filter expression over items). Adding a section = add an entry + tokens color + locale label.

### 7.3 `taxonomy/item-types.yaml`

Each type: `id`, `label` (locale key), `schema` (`schema/item-types/<id>.schema.json` for the `detail` object), `component` (site component name), `blocks` (ordered deep-dive blocks the component renders), `brief_fields`, `markdown_fields`. Default types: `model_release`, `tool_release`, `framework_release`, `paper`, `article`, `repo`, `security_advisory`, `industry`, `leaderboard_shift`. Adding a type = schema file + component + registry entry (+ locale labels).

### 7.4 `sources/registry/*.yaml` (validated by `schema/source.schema.json`)

```yaml
- id: hf-daily-papers
  name: Hugging Face Daily Papers
  tier: T1-data
  sections: [research]
  via: collector
  collector:
    kind: json                       # rss | atom | json | json-snapshot-diff
    url: "https://huggingface.co/api/daily_papers?date={date}"
    items: "[*]"
    fields: { id: "paper.id", title: "paper.title", url: "join('', ['https://huggingface.co/papers/', paper.id])",
              published: "publishedAt", summary: "paper.summary", signal: "paper.upvotes" }
  trust: 4
- id: claude-code-releases
  name: Claude Code releases
  tier: T1
  sections: [tooling]
  via: mcp
  mcp: { server: github, tool: list_releases, args: { owner: anthropics, repo: claude-code } }
- id: openrouter-models
  tier: T1-data
  sections: [models]
  via: collector
  collector: { kind: json-snapshot-diff, url: "https://openrouter.ai/api/v1/models", items: "data[*]",
               key: "id", track: ["pricing", "context_length"] }
```
Template variables: `{date}`, `{since}`, `{until}`, `{config.*}`. The collector is generic: kinds, mapping, auth (header from env var name), rate limits, retries, caching are declared per entry. MCP-backed entries tell the researcher which server/tool to call. Default registry covers the sources in §11.

### 7.5 MCP server catalog (`plugins/pulse/mcp/servers.yaml`)
Per server: id, package/command (pinned version, Renovate-managed), transport, required env vars, network domains (feeds the cloud allowlist), read-only flag. `pulse mcp sync` writes the instance `.mcp.json` from enabled servers; `pulse doctor --allowlist` derives the cloud network allowlist from catalog + registry domains.

## 8. Daily run flow (`/pulse:daily`)

Working directory `runs/<date>/`; each step writes a checkpoint; `--resume` continues; `--fixtures <dir>` runs offline against recorded inputs (evals).

1. **Load memory.** Load config + merged registries (engine defaults + instance overrides), acquire `state/lock.json`, compute the window from the last successful run (cap `window.max_hours`; beyond → catch-up digest). Load the 30-day coverage view, threads, last 7 reports.
2. **Parallel research.** One `section-researcher` subagent per enabled section (brief and rubric from the section registry) plus the research desk pipeline (§10). Each runs `pulse collect --section <id>` (generic collector over that section's registry entries), calls the MCP tools listed for its sources, uses WebSearch/WebFetch/Exa for discovery, reads full primary sources, and writes `candidates.<section>.json` (schema: `candidate.schema.json`, every number with `source_ref` + quote).
3. **History check.** `pulse history check` — exact URL (courlan-normalized) and entity-key matches, plus "same product, new version"; Claude judges semantic overlap → drop / update (link `update_of`) / upgrade (rumor → confirmed); thread ids assigned.
4. **Verify.** `verifier` subagent: ≥1 T1 source fetched this run (`pulse verify links`), date inside window, faithful summary, every number matches its quote. Assign impact/novelty/relevance per the section rubric and confidence (Confirmed/Reported/Rumor). Rejections recorded with reasons.
5. **Write.** Editor composes `report.json` (validated by `report.schema.json` via `pulse validate`), including generative visual specs following the `pulse-design` skill. Recall check against T2 curators + HN front page.
6. **Build + review.** `pulse site build` (builds `@pulseai/site` against the instance content) → `pulse shoot` (Playwright: light, dark, mobile) → axe-core audit → `design-reviewer` scores screenshots against the rubric (`quality.design_review_min_score`); failing visuals get ≤`limits.design_fix_rounds` fixes, then fall back to simpler blocks. `single-file-cli` produces `report.single.html`; `vl-convert` renders static chart images for Markdown/notifications.
7. **Publish.** `pulse publish`: write `reports/YYYY/MM/DD/`, update `state/`, commit, push to `publish.branch`. Cloudflare Pages rebuilds the site. Release lock.
8. **Notify.** `pulse notify` → Apprise: headline, Pulse score, TL;DR, deep links to top 3, PNG or GIF. Failure path sends step + run link. Notification failure never reverts a publish.

## 9. Report data model

Defined in `schema/report.schema.json`, `item.schema.json`, `visual.schema.json`, `item-types/*.schema.json`. Python models are generated; the site builds Zod schemas from the same files.

- **Report:** `schema_version`, `meta` (date, edition, window, language, engine version, host, models, run stats, cost, source health, sample flag, mode normal|plain|catch_up), `headline`, `pulse_score` {value, avg_7d}, `kpis[]`, `tldr[]`, `front_page` (dashboard layout), `items[]`, `adoption_radar[]`, `action_list[]` (≤3), `signals[]`, `corrections[]`, `research` (desk extras: paper_of_the_day, venue_watch), `methodology`.
- **Item (common):** `id` (ASCII slug, permalink), `section` (must exist in sections registry), `type` (must exist in item-types registry), `title`, `entity_key`, `thread_id`, `update_of?`, `impact`, `novelty`, `relevance`, `confidence`, `summary`, `why_it_matters`, `what_to_do?`, `caveats?`, `sources[]` {url, title, tier, kind primary|secondary, fetched_at}, `facts[]` {label, value, unit, source_ref, quote}, `visuals[]`, `images[]` {url, caption, credit, alt, license}, `detail` (validated by the type's schema).
- **Cross-reference rules** (validated by `pulse validate`, which combines JSON Schema with registry-aware checks): unique item/visual ids; TL;DR/radar/actions reference existing items; confirmed items have a primary T1 source; facts reference existing sources; rumors only in signals; paper_of_the_day is a paper item; section/type ids exist in registries.
- **Visual** (discriminated by `kind`): `vega-lite` (inline `data.values` only; no remote data), `mermaid`, `table`, `dashboard` (layout of tiles/charts/tables), `image-ref`, `motion` (GIF/animated SVG asset), `custom-html` (sandboxed, last resort). Every visual: `id`, `title`, `alt`, `source_note`.

Default item types and deep-dive blocks (registry defaults, extendable):

| Type | Blocks |
|---|---|
| `model_release` | key facts (context, price, modalities, availability, weights/license), benchmarks vs prior best, price comparison, try-it, archive history |
| `tool_release` / `framework_release` | changelog highlights (new/fix/breaking/perf/deprecation), cadence, adoption verdict, snippet, migration notes |
| `paper` | §10.3 paper brief |
| `article` | key points, reading time, worth-reading-in-full verdict |
| `repo` | stars trend, language, license, last commit, maintainer activity, alternatives, quickstart |
| `security_advisory` | severity meter, affected/fixed versions, exploited-in-wild, fix command |
| `industry` | who/what/how much, related-events timeline, builder impact |
| `leaderboard_shift` | before/after ranks, movers, reliability note |

Items with `impact < deep_dive.min_impact` render as compact briefs.

## 10. Research desk

### 10.1 Sources (registry defaults)
- **Preprints:** arXiv (configured categories) via `arxiv-mcp-server` and/or collector RSS.
- **Peer-reviewed:** OpenReview (`openreview-py`), ACL Anthology, PMLR, CVF Open Access, USENIX, ICSE/FSE (collector feeds/pages).
- **Signals:** HF Daily Papers (collector or HF MCP), alphaXiv, Semantic Scholar (`semanticscholar`), OpenAlex (`pyalex`), code/weights availability, T2 mentions.
- **Lab research:** Anthropic research + transformer-circuits.pub, OpenAI, Google DeepMind/Research, Meta FAIR, Microsoft Research, Apple ML, NVIDIA, AI2, Stanford HAI/CRFM, BAIR, METR, Epoch AI.
- **Long-form articles:** engineering blogs (Anthropic Engineering, OpenAI Cookbook, GitHub, Cloudflare, Vercel, …), expert writers (Lilian Weng, Chip Huyen, Sebastian Raschka, Eugene Yan, Hamel Husain, Andrej Karpathy, Jay Alammar), publications (Quanta, IEEE Spectrum, ACM Queue, MIT Technology Review, The Gradient).

### 10.2 Pipeline
1. **Triage** (`paper-triage`): 300–600 new papers/day → score title+abstract against rubric + interests → ~30.
2. **Enrich:** venue/peer-review, affiliations, author record, upvotes, code/weights, T2 mentions → top `max_papers_deep` + briefs.
3. **Full read** (`paper-analyst`): arXiv HTML first, PDF fallback; reviewer-grade reading.
4. **Paper brief** → deep-dive.

### 10.3 Paper brief
One-line TL;DR · plain-language explanation · problem · key idea · method steps (→ Mermaid diagram) · results vs baselines (numbers with table/figure refs → chart) · **critical review** (limitations, contamination risk, sample size, compute cost, cherry-picking concerns) · reproducibility (code, data, weights, license) · practical takeaway · **reading guide** (sections to read, glossary, reading time, difficulty) · real figures (captioned, credited; hotlinked, copied only if license allows) · related/prior work and prior Pulse coverage.

### 10.4 Layout
Driven by the research section's `groups` in `taxonomy/sections.yaml`: Paper of the day → Top papers → Also notable → Long reads → Venue watch.

## 11. Sources & quality rules

### 11.1 Tiers (default registry content)

| Tier | Role | Examples |
|---|---|---|
| T1 primary (required per item) | Official word | Lab newsrooms/API changelogs (Anthropic, OpenAI, Google DeepMind, Meta, Mistral, DeepSeek, Qwen, xAI, NVIDIA, Microsoft); GitHub releases watchlist (claude-code, codex, gemini-cli, Cursor changelog, opencode, MCP spec + servers, Agent SDKs, LangGraph, Pydantic AI, Mastra, Vercel AI SDK, vLLM, SGLang, llama.cpp, Ollama, Transformers); official MCP registry; `anthropics/claude-plugins-official`; `anthropics/skills`; model cards |
| T1 data | Numbers | OpenRouter models (snapshot diff), HF Daily Papers, arXiv, HF trending, GitHub search, SWE-bench, LMArena, Epoch AI, Artificial Analysis (optional key), GitHub Advisory DB, OSV, CISA KEV |
| T2 curators (signal only) | Importance | Simon Willison, Latent Space/AINews, Interconnects, Import AI, Ahead of AI, The Batch, HN front page, Lobsters, r/LocalLLaMA |
| T3 discovery | Recall | WebSearch/WebFetch, Exa/Brave MCP |
| Blocked | — | Content farms, SEO listicles, AI-generated news sites, re-post aggregators (blocklist in registry) |

### 11.2 Ranking
Impact (1–5, rubric per section in registry), Novelty (1–5), Relevance (interests; never drops a major out-of-interest item), Pulse score = Σ impact of published items vs 7-day average.

### 11.3 Coverage memory
`state/coverage.jsonl` (schema: `coverage.schema.json`): per published item — normalized `entity_key`, canonical URL, title, short summary, date, `thread_id`, `item_id`. `state/threads.jsonl` for story threads. `state/snapshots/` for snapshot-diff collector kinds.

### 11.4 Reliability rules (enforced by CLI gates, not only prompts)
1. ≥1 T1 source fetched during this run; link check confirms HTTP 200 and entity mention.
2. Publish date inside the window; undated → excluded unless official changelog.
3. Every number has `source_ref` + `quote`; verifier re-checks; mismatches dropped.
4. Confidence routing per `confidence` config.
5. Prompt-injection hygiene: fetched content is data; research subagents get read-only tools; MCP servers marked read-only; nothing fetched can trigger write/push/notify.
6. Recall check vs T2 curators + HN front page.
7. Corrections recorded and coverage amended.
8. Summaries in Claude's own words; short quotes only; source HTML sanitized with nh3.

## 12. Site, report template & visual system (Astro)

### 12.1 Content and routes
- Content collection `reports` (glob loader over instance `reports/**/report.json`), schema built with `z.fromJSONSchema(report.schema.json)` + registry-aware refinements.
- Routes: `/` (latest), `/YYYY/MM/DD/`, `/archive/` (calendar heatmap by Pulse score), `/threads/<id>/`, `/entities/<key>/`, `/trends/` (30-day), `/health/` (system health), localized via Astro i18n with `locales/*.json`.
- Pagefind index built post-build; sitemap; RSS feed of reports.

### 12.2 Fixed frame (components, not model-editable)
Masthead (edition, date/window, headline, Pulse score, theme switch) → KPI tiles → TL;DR → generative front-page dashboard → adoption radar → sections in registry order (filter row: section, type, min impact, confidence, new vs update; Expand/Collapse all) → action list → signals → corrections → methodology & source health footer. Items are native `<details>/<summary>` with stable permalinks; print expands all; works without JS (charts fall back to data tables).

### 12.3 Item rendering
`components/items/<Type>.astro` per registry type renders that type's blocks; a generic `ItemShell` renders shared parts (kicker, title, badges, summary, facts, visuals, images, why/caveats/what-to-do, sources). Brief vs deep-dive decided by `deep_dive.min_impact`.

### 12.4 Generative visual blocks
| Kind | OSS renderer | Notes |
|---|---|---|
| `vega-lite` | vega-embed island; `vl-convert` for static | Theme config generated from tokens (light/dark); inline data only |
| `dashboard` | Astro grid component | Tiles/charts/tables from a layout spec |
| `mermaid` | astro-mermaid | Theme variables from tokens |
| `table` | DataTable component | Also the no-JS fallback for charts |
| `image-ref` | Astro `<Image>` | Real images only: paper figures, Playwright screenshots, OG images; caption/credit/alt/license required |
| `motion` | gifski / animated SVG | Respects `prefers-reduced-motion` |
| `custom-html` | sandboxed `<iframe srcdoc>` (no network, CSP) | Last resort, strictest lint |

### 12.5 Design rules and enforcement
- `pulse-design` skill (form choice, color by job, one y-axis, ≤8 series, direct labels, thin marks, diagram limits, image/motion/a11y rules, good/bad examples).
- Gates in order: (1) JSON Schema for every visual; Vega-Lite compiled with `vl-convert` (catches invalid specs); Mermaid parsed; (2) design lint (tokens only — no raw colors in specs, required title/alt/source, no dual axis, ≤8 series); (3) token validation (ColorAide ΔE/CVD against `quality.*` thresholds); (4) axe-core audit on rendered pages; (5) design-reviewer vision rubric on light/dark/mobile → fix rounds → fallback.

### 12.6 Themes
- Tokens in DTCG JSON: `tokens/base/*.json`, `tokens/themes/<preset>/{light,dark}.json`; Style Dictionary emits CSS custom properties, Vega-Lite configs, Mermaid theme variables.
- Presets: `pulse`, `paper`, `terminal`; custom preset = new folder in instance `tokens/themes/`.
- Reader toggle Auto/Light/Dark, persisted per viewer (guarded localStorage), `?theme=` override, live chart re-theming.
- Starting palette (validated 2026-10-11 against the thresholds above): sections light `#2a78d6 #eb6834 #1baf7a #eda100`, dark `#3987e5 #d95926 #199e70 #e6b000` (min ΔE 13.7 light / 20.9 dark; min protan/deutan ΔE 9.1 / 9.4).

## 13. Hosts

| | Cloud routine | GitHub Actions | Local |
|---|---|---|---|
| Trigger | Routine schedule from `pulse schedule print --host routine` (on-the-hour times offset by `cloud_offset_minutes_when_on_hour`) | `schedule: cron` (UTC) from `pulse schedule print --host actions` (+ DST guard for DST zones) + `workflow_dispatch` | systemd user timer (`OnCalendar=… <tz>`, `Persistent=true`) / launchd plist, generated by `pulse schedule print` |
| Repo | `pulse-instance` only (single repo → repo hooks load) | Workflow in the private instance repo | Local clone |
| Auth | Subscription | `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` | Subscription login or API key |
| Plugin | `.claude/settings.json` marketplace + `enabledPlugins`; fallback setup-script install | Action `plugin_marketplaces` + `plugins` inputs | `claude plugin install pulse@pulseai` |
| MCP | Instance `.mcp.json` (stdio servers in the VM) and/or claude.ai connectors | `--mcp-config .mcp.json` via `claude_args` | `.mcp.json` |
| Environment | Setup script installs uv, pnpm, Chromium, CLI (cached); network allowlist from `pulse doctor --allowlist` (or Full) | Steps install the same; SHA-pinned actions | Same toolchain |
| Command | `/pulse:daily` | `prompt: "/pulse:daily"` | `claude -p "/pulse:daily" --permission-prompts none --allowedTools <generated list>` |
| Secrets | Environment variables / network secrets | Repo secrets | `~/.config/pulse/env` (0600) |

**Guardrail hooks** (plugin): deny push/notify/writes outside `runs/` during research phases; Stop hook verifies `pulse validate` passed. CLI gates enforce the same rules independently of hooks.

## 14. Storage, publishing, notifications
- **Storage:** `reports/YYYY/MM/DD/` with `report.json`, `report.md`, `report.single.html`, `assets/` (static chart images, screenshots, GIFs).
- **Private viewing:** Cloudflare Pages builds the instance (`@pulseai/site`) on push; Cloudflare Access (email OTP) protects it. GitHub Pages documented for public instances (Pages from a private repo is still public on non-Enterprise plans).
- **Notifications:** Apprise URLs from `PULSE_NOTIFY_URLS`; message = headline, Pulse score, TL;DR, deep links to top 3, PNG/GIF; failure alerts with failed step and run link.

## 15. Failure handling
- Checkpoints per step; `--resume`.
- Source failure → tenacity retries → skip + mark in source health; >30% T1 failures → banner.
- Section agent failure → "Section unavailable" placeholder; report still ships.
- Validation failure after fix rounds → **plain edition** + alert.
- Lock with stale timeout (`limits.run_minutes × 2`); same-date rerun overwrites and keeps edition number.
- Missed days → window from last success, capped; beyond → catch-up digest.
- Limits: `agent_max_turns`, `run_minutes`, `max_budget_usd`.
- Notify best-effort; never reverts publish.

## 16. Testing & CI
- **Python:** pytest (collector kinds with recorded HTTP fixtures, registry merge, history matching, schedule/DST, validate cross-refs, notify message building), Pyright strict, Ruff.
- **Site:** Vitest (schema loading, registry→component mapping), `astro check`, Biome; Playwright E2E on example reports (theme switch, expand/collapse, filters, permalinks, no-JS fallback, print), **visual regression** (light/dark/mobile), **axe-core** audits (zero serious/critical violations).
- **Schemas & registries:** `check-jsonschema` over all registries, configs, examples; generated-model drift check.
- **Agent evals (frozen day):** `/pulse:daily --fixtures <day>`: schema-valid output, every number traced to a quote, planted major items included, planted duplicate dropped/marked update, planted prompt-injection page ignored, design-review score ≥ threshold. Packaged as `claude plugin eval` suites.
- **CI:** all of the above on every PR; `claude plugin validate`; build and deploy the public demo site from `examples/`; Renovate PRs must pass the same gates.
- **User setup:** `pulse doctor` (versions, auth, MCP servers reachable, allowlist, secrets, push permission dry-run, notifier test).

## 17. Observability & cost
`runs/<date>/run.json` (schema: `run.schema.json`): duration, tokens/cost per agent and model, funnel (scanned → triaged → verified → published), source health, gate results, design-review scores, recall misses. Structured logs (structlog JSON). Optional Claude Code OpenTelemetry export. System health page on the site. Subscription hosts draw plan usage; API hosts capped by `limits.max_budget_usd`; real cost measured in first dry runs and documented.

## 18. Security & privacy
- Public engine has no personal data or secrets; instance repo is private.
- Secrets only in host secret stores/env files; `pulse doctor` scans the instance for committed secrets; GitHub secret scanning on.
- Fetched content untrusted (rule 11.4.5); source HTML sanitized (nh3); custom HTML visuals sandboxed with CSP.
- Workflows least-privilege; actions SHA-pinned; CodeQL + dependency review.
- Runs push only to the configured instance repo/branch.

## 19. Risks and open questions (first spikes)
1. Plugin auto-install in cloud routine sessions via project settings — verify; fallback setup-script install.
2. Routine push to `main` of the instance repo — verify; fallback push to a `claude/` branch + auto-merge workflow.
3. Cloud network allowlist coverage for registry/MCP domains and WebFetch behavior — verify; fallback Full network.
4. Stdio MCP servers inside cloud routine VMs (startup time, caching via setup script) — verify; fallback claude.ai connectors where available.
5. Cloudflare Pages build of `@pulseai/site` from the instance (Node/pnpm versions, build time) — verify.
6. Run duration/cost on Opus roles — measure; tune `models_by_role`.
7. Source API terms/rate limits (Semantic Scholar, OpenReview, alphaXiv, Reddit) — verify per registry entry; mark optional where keys are needed.
8. `astro-mermaid` vs Mermaid client rendering for no-JS output — evaluate in M3.

## 20. Delivery milestones (each becomes its own implementation plan)
- **M0 Spikes:** risks 1–5 on a throwaway instance.
- **M1 Foundation:** monorepo scaffold (uv + pnpm workspaces), CI, Renovate, release-please, pre-commit; `schema/` + model generation; registries (sections, item types, locales, tokens) with loaders/merge; `pulse validate`, `pulse schedule`, `pulse doctor` (basic).
- **M2 Site & visual system:** Astro site package, frame components, per-type item components, VegaLite/Mermaid/DataTable/Dashboard components, Style Dictionary pipeline + theme switch, Pagefind, example reports, Playwright + axe + visual regression.
- **M3 Data access:** generic collector (rss/atom/json/snapshot-diff), MCP catalog + `pulse mcp sync`, default source registry, history store, link verification.
- **M4 Agents & skills:** `/pulse:daily` orchestrator, section researcher, verifier, design-reviewer loop, guardrail hooks, design lint, evals.
- **M5 Research desk:** paper triage/analyst, research enrichment sources, paper brief component, long reads, venue watch.
- **M6 Publish, notify, hosts:** `pulse publish/notify/shoot`, single-file export, routine + Actions + local adapters, `pulse init`, Cloudflare docs, quickstarts, public demo site.

## 21. References consulted (2026-10-11)
- Claude Code: routines https://code.claude.com/docs/en/routines · GitHub Actions https://code.claude.com/docs/en/github-actions · headless https://code.claude.com/docs/en/headless · cloud environments https://code.claude.com/docs/en/cloud-environments · desktop scheduled tasks https://code.claude.com/docs/en/desktop-scheduled-tasks · changelog https://code.claude.com/docs/en/changelog
- Plugins/skills: https://github.com/anthropics/claude-plugins-official · https://github.com/anthropics/skills
- OSS components: https://github.com/withastro/astro · https://github.com/Pagefind/pagefind · https://github.com/style-dictionary/style-dictionary · https://github.com/vega/vega-lite · https://github.com/mermaid-js/mermaid · https://github.com/microsoft/playwright-mcp · https://github.com/caronc/apprise · https://github.com/blazickjp/arxiv-mcp-server · https://github.com/github/github-mcp-server · https://github.com/huggingface/hf-mcp-server · https://github.com/modelcontextprotocol/servers · https://github.com/exa-labs/exa-mcp-server · https://github.com/brave/brave-search-mcp-server · https://github.com/renovatebot/renovate · https://github.com/googleapis/release-please · https://github.com/gildas-lormeau/single-file-cli
- Prior art: https://github.com/kippapollo/ai-news · https://github.com/abdooay/ai-news-digest · https://github.com/rogeriomoura/ai-daily-digest · https://github.com/srijit316/daily_research_digest · https://github.com/frankzch/ai-news-brief
