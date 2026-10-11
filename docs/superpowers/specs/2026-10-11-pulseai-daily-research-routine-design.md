# PulseAI — Daily AI & Software Research Routine — Design Spec

- **Date:** 2026-10-11
- **Status:** Draft for review
- **Owner:** @Mordris

## 1. Purpose

Staying current in AI and software is hard: models, agent tooling, papers, and open source move daily. PulseAI is a Claude Code–driven routine that, once per day, researches what changed, verifies it against primary sources, compares it to what it already reported, and publishes **one** heavily visualized, consistently designed report, then notifies the reader.

It is a **public GitHub project** so anyone can run their own instance in ~15 minutes. Daily reports are private to each instance; the public repo ships only a few example reports.

### Success criteria

1. One report per day arrives at the configured time (default start **17:00 Europe/Istanbul**), on any of three hosts.
2. The reader never misses a major model release, tool release, notable paper, or important OSS/security event in the configured interest area.
3. Every item is traceable to a primary source fetched during the run; every number in a chart traces to a quoted source span.
4. Every report has the same recognizable structure and design system, while visuals are generated per item and pass automated design checks in light, dark, and mobile.
5. A stranger can go from zero to first report in ≤15 minutes using the docs and `pulse doctor`.

### Non-goals (v1)

- AI-generated images (decided: **real images only**; charts/diagrams/GIFs remain generative).
- Multi-user accounts, comments, or a hosted SaaS.
- Weekly/monthly editions (the archive and story threads make them easy later; out of scope now).
- Real-time alerts during the day.

## 2. Decisions log (agreed during brainstorming)

| # | Decision |
|---|---|
| D1 | Support **three hosts** via thin adapters over one core: Claude Code cloud **routine**, **GitHub Actions** (`claude-code-action@v1`), **local** (systemd/launchd + `claude -p`). |
| D2 | Reports stored in a **private repo** with a static site. |
| D3 | Coverage: **Models & labs**, **Agentic dev tooling**, **Research desk** (papers + articles), **Software & OSS** (incl. security). |
| D4 | Notifications are **pluggable** (Telegram, email, Slack, Discord, ntfy) — implemented with Apprise. |
| D5 | Language **configurable**, default English. |
| D6 | **Claude drives the whole run** (search/collect → curate → compare with history → write → design → publish → notify). Scripts are tools Claude calls, not a separate pipeline. |
| D7 | Schedule **configurable**; default start 17:00 Europe/Istanbul. |
| D8 | **Fixed frame + generative visuals**: template and design tokens are locked; Claude designs per-item charts, dashboards, diagrams, motion, and uses real images — constrained by a design skill and enforced by automated gates. |
| D9 | Every item expands into a **type-specific deep-dive** with visualizations, not just a link. |
| D10 | **Dark/light theme switch** (Auto/Light/Dark), configurable presets and overrides. |
| D11 | Research desk with full-text **paper understanding** and long-form **articles**; academic sources beyond arXiv. |
| D12 | Default interests profile: **agents + Claude Code + MCP** (plus general frontier AI). |
| D13 | **Two repos**: public engine `PulseAI` + private `pulse-instance` per user. Private viewing via **Cloudflare Pages + Cloudflare Access**; GitHub Pages optional for public instances. |

## 3. Architecture overview

```
                    ┌──────────── Host adapter (one of) ─────────────┐
                    │ Cloud routine │ GitHub Actions │ systemd/launchd│
                    └──────────────┬─────────────────────────────────┘
                                   │ runs `/pulse:daily` in a clone of pulse-instance
                                   ▼
┌──────────────────────── Editor-in-chief (main session, Opus) ───────────────────────┐
│ 1 Load memory → 2 Parallel research → 3 History check → 4 Verify → 5 Write          │
│ → 6 Render + design review → 7 Publish → 8 Notify                                   │
│                                                                                     │
│ Subagents: models-researcher · tooling-researcher · oss-researcher ·               │
│            paper-triage · paper-analyst · verifier · design-reviewer               │
│ Tools:     WebSearch/WebFetch · optional MCPs (Exa, Jina/Firecrawl) · `pulse` CLI   │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                   │ git push
                                   ▼
            pulse-instance (private): reports/ · state/ · site/  ──▶ Cloudflare Pages (+Access)
                                   │
                                   ▼
                       Apprise → Telegram / email / Slack / Discord / ntfy
```

**Principle:** the model produces *validated data and constrained visual specs*; deterministic code renders the frame. Freedom where it adds value (what to cover, how to explain, how to visualize), determinism where consistency matters (structure, tokens, theming, validation).

## 4. Repositories

### 4.1 `PulseAI` (public engine)

```
.claude-plugin/marketplace.json          # repo is a Claude Code plugin marketplace
plugins/pulse/
  .claude-plugin/plugin.json
  skills/
    daily/SKILL.md                       # orchestrator: /pulse:daily
    pulse-design/SKILL.md + references/  # design rules for all visuals
    paper-brief/SKILL.md                 # how to read & brief a paper
    source-vetting/SKILL.md              # tiers, dating, citation rules
  agents/
    models-researcher.md  tooling-researcher.md  oss-researcher.md
    paper-triage.md  paper-analyst.md  verifier.md  design-reviewer.md
  hooks/hooks.json                       # guardrails (see §11)
pulse/                                   # Python package + CLI (uv)
  fetchers/   rss.py arxiv.py hf_papers.py openrouter.py github.py hn.py
              semantic_scholar.py openalex.py openreview.py osv.py mcp_registry.py
  schema/     models.py (Pydantic) → report.schema.json, item types
  history/    coverage store, entity keys, story threads
  render/     templates/ (Jinja2), components/, vega theme, layout DSL renderer
  lint/       design_lint.py, palette_validate, linkcheck.py, svg_sanitize.py
  shoot/      Playwright screenshots, GIF capture (gifski)
  publish/    git commit/push, site index, Pagefind index
  notify/     Apprise wrapper, message builder
  schedule/   config time+tz → per-host schedule artifacts
  doctor/     setup checks, network allowlist generator
themes/       pulse/  paper/  terminal/       # tokens.yaml (light + dark)
sources/sources.yaml                         # default source registry
adapters/
  routine/          prompt.md, setup.sh, README (env + allowlist)
  github-actions/   daily.yml
  local/            pulse.service, pulse.timer, com.pulseai.daily.plist, run.sh
templates/instance/                          # skeleton for `pulse init` / "Use this template"
examples/                                    # 2–3 real example reports (public demo site)
docs/                                        # quickstart per host, customizing sources/themes
tests/
```

### 4.2 `pulse-instance` (private, per user)

```
pulse.config.yaml
sources.local.yaml            # optional overrides/additions
.claude/settings.json         # marketplace + enabledPlugins for pulse
.github/workflows/daily.yml   # only if using the Actions host
reports/YYYY/MM/DD/{index.html, report.json, report.md, assets/}
state/{coverage.jsonl, threads.jsonl, last_run.json, lock.json, snapshots/}
runs/YYYY-MM-DD/              # checkpoints + run.json (git-ignored except run.json)
site/                         # built archive, trends, entity pages, Pagefind index
```

The engine is consumed as a plugin from the public marketplace and as a CLI via `uvx --from git+https://github.com/<owner>/PulseAI@<tag> pulse`. Instances pin an engine tag by default (`engine.version` in config).

## 5. Configuration (`pulse.config.yaml`)

```yaml
engine: { version: "v1.0.0" }            # or "main"
schedule: { time: "17:00", tz: "Europe/Istanbul" }
language: en
interests:
  weight_high: [claude code, agentic coding, mcp, skills, plugins, agent frameworks,
                llm reasoning, evals]
  weight_normal: [frontier models, open-weights models, inference, ai security]
sections:
  models:   { enabled: true, max_items: 8 }
  tooling:  { enabled: true, max_items: 10 }
  research: { enabled: true, max_papers_deep: 6, max_briefs: 10, max_long_reads: 4,
              arxiv_categories: [cs.AI, cs.CL, cs.LG, cs.SE, cs.CV, cs.MA, cs.IR, cs.CR, cs.DC, cs.PL, stat.ML] }
  oss:      { enabled: true, max_items: 8, security: true }
deep_dive: { min_impact: 3 }              # below → compact brief
confidence: { include_reported: signals_box, include_rumor: false }
window: { max_hours: 72 }                 # beyond → catch-up digest
models_by_role:
  editor: claude-opus-5-5
  paper_analyst: claude-opus-5-5
  verifier: claude-opus-5-5
  researchers: claude-sonnet-5-5
  triage: claude-haiku-5-5
  design_reviewer: claude-sonnet-5-5
limits: { run_minutes: 45, max_budget_usd: 15, design_fix_rounds: 2 }
theme:
  default: auto                           # auto | light | dark
  switcher: true
  preset: pulse                           # pulse | paper | terminal | custom
  overrides: { }                          # accent, fonts, section colors
visuals: { min_per_deep_dive: 1, motion: true, notify_media: png }   # png | gif
site: { url: "https://pulse.example.com", search: true }
publish: { repo: "<owner>/pulse-instance", branch: main }
notify:
  urls_env: PULSE_NOTIFY_URLS             # Apprise URLs, comma-separated, from secrets
  on_failure: true
```

`pulse schedule print --host {routine|actions|systemd|launchd}` derives host schedules from `schedule` (e.g. 17:00 Europe/Istanbul → Actions `cron: "7 14 * * *"`; routines get 17:07 local because on-the-hour runs may start late). Changing the time is a one-line config edit plus re-running the print/apply step.

## 6. Daily run flow (`/pulse:daily`)

Working directory: `runs/<date>/`. Each step writes a checkpoint; `/pulse:daily --resume` continues from the last good step; `--fixtures <dir>` runs offline against recorded inputs (evals).

1. **Load memory.** Read config, acquire `state/lock.json` (exit if another host holds a fresh lock), compute window = `last_successful_run → now` (cap `window.max_hours`; beyond → catch-up digest mode). Load `coverage.jsonl` (last 30 days compact view), `threads.jsonl`, last 7 `report.json`.
2. **Parallel research.** Spawn section subagents (Sonnet): `models-researcher`, `tooling-researcher`, `oss-researcher`, and the research desk (`paper-triage` → `paper-analyst`, §8). Each:
   - calls `pulse fetch <source>` for its registry sources (APIs/RSS/releases),
   - runs WebSearch/WebFetch (and optional MCPs) for discovery and gap-filling,
   - reads full primary sources for kept candidates and extracts structured facts with `source_ref` + quoted span for every number,
   - returns `candidates.<section>.json`.
3. **History check.** `pulse history check` does exact matching on canonical URL and entity key (e.g. `anthropic/claude-code@2.1.296`). Claude then judges semantic overlap against the 30-day view: **drop** (nothing new), **update** (new facts → `update_of` link), **upgrade** (rumor → confirmed). Story `thread_id` assigned/extended.
4. **Verify.** `verifier` subagent (Opus) per item: ≥1 T1 source fetched this run (`pulse lint links` — HTTP 200 and page mentions the entity), publish date inside window, claim/summary faithful, every number matches its quoted span. Assign **Impact 1–5** (per-section rubric), **Novelty 1–5**, **Relevance** (vs interests), **Confidence** (Confirmed / Reported / Rumor). Failures are cut with a recorded reason.
5. **Write.** Editor composes `report.json` (schema §7): headline, Pulse score, TL;DR, sections, deep-dives, briefs, adoption verdicts, action list, signals box, corrections, methodology. Visual specs per item following `pulse-design`. Recall check: compare against latest T2 curator posts + HN front page; investigate any major miss before finalizing.
6. **Render + design review.** `pulse validate` (schema) → `pulse lint design` → `pulse render` (HTML single-file, Markdown, static SVG/PNG for charts) → `pulse shoot` (light, dark, 390px mobile) → `design-reviewer` subagent scores screenshots against the rubric; failing visuals get ≤2 fix rounds, then fall back to a simpler block. Never ship a broken visual.
7. **Publish.** `pulse publish`: write `reports/YYYY/MM/DD/`, update `state/` (coverage, threads, last_run), rebuild `site/` (archive heatmap, entity/thread pages, trends, Pagefind index), commit and push to `publish.branch`. Cloudflare Pages deploys on push. Release lock.
8. **Notify.** `pulse notify`: headline, Pulse score, TL;DR, deep links to top 3 items, front-page PNG (or 10-s GIF). Failure path sends step + run link. Notification failure never reverts a publish.

## 7. Report data model (`report.json`)

Top level (Pydantic models; JSON Schema exported and used with `--json-schema` where helpful):

- `meta`: date, edition, window {start, end, tz}, language, engine version, models used, host, run stats (scanned/triaged/verified/published), cost, source health[].
- `headline`, `pulse_score` {value, avg_7d, delta}.
- `kpis[]`: label, value, delta, sparkline series.
- `tldr[]`: text, section, item_id, confidence.
- `front_page`: dashboard layout (§9.2) — generative.
- `sections[]`: id (`models|tooling|research|oss`), items[], plus research desk sub-blocks (paper_of_the_day, top_papers, also_notable, long_reads, venue_watch).
- `adoption_radar[]`: item_id, ring (`adopt|trial|assess|hold`), rationale.
- `action_list[3]`, `signals[]` (Reported items), `corrections[]`, `methodology`.

**Item** (common): `id` (slug, permalink anchor), `type`, `section`, `title`, `entity_key`, `thread_id`, `update_of?`, `impact`, `novelty`, `relevance`, `confidence`, `summary`, `why_it_matters`, `what_to_do`, `caveats`, `sources[]` {url, tier, kind: primary|secondary, fetched_at, title}, `facts[]` {label, value, unit, source_ref, quote}, `visuals[]` (§9.2), `images[]` {url|asset, caption, credit, alt, license}, `detail` (type-specific).

**Item types and their deep-dive `detail`:**

| Type | Detail fields → rendered blocks |
|---|---|
| `model_release` | key facts (context, price in/out, modalities, availability, weights/license), benchmarks[] vs prior best, price comparison, try-it snippet, archive history |
| `tool_release` / `framework_release` | changelog highlights[] {tag: new\|fix\|breaking, text}, version cadence series, adoption verdict, what-to-do snippet, migration notes |
| `paper` | §8.3 paper brief |
| `article` | key points[], reading time, worth-reading-in-full verdict + reason |
| `repo` | stars series, language, license, last commit, maintainers activity, alternatives[], quickstart |
| `security_advisory` | severity (CVSS), affected versions, exploited-in-wild (KEV), fix/upgrade command |
| `industry` | who/what/how much, related-events timeline from threads, builder impact |
| `leaderboard_shift` | before/after ranks, movers, benchmark reliability note |

Items with `impact < deep_dive.min_impact` render as compact **briefs** (summary + sources, expandable).

## 8. Research desk

### 8.1 Sources
- **Preprints:** arXiv (configured categories) via API/RSS.
- **Peer-reviewed:** OpenReview (ICLR, NeurIPS, ICML, COLM — submissions, reviews, scores, decisions), ACL Anthology, PMLR, CVF Open Access, USENIX (OSDI/SOSP/Security), ICSE/FSE.
- **Signals:** HF Daily Papers (upvotes), alphaXiv (trending/discussion), Semantic Scholar API (citations, influential citations, author record, recommendations), OpenAlex (citation graph), code/weights availability + stars, T2 mentions.
- **Lab research:** Anthropic research + transformer-circuits.pub, OpenAI, Google DeepMind/Research, Meta FAIR, Microsoft Research, Apple ML, NVIDIA, AI2, Stanford HAI/CRFM, BAIR, METR, Epoch AI.
- **Long-form articles:** engineering blogs (Anthropic Engineering, OpenAI Cookbook, GitHub, Cloudflare, Vercel, …), expert writers (Lilian Weng, Chip Huyen, Sebastian Raschka, Eugene Yan, Hamel Husain, Andrej Karpathy, Jay Alammar), publications (Quanta, IEEE Spectrum, ACM Queue, MIT Technology Review, The Gradient).

### 8.2 Pipeline
1. **Triage** (`paper-triage`, Haiku): 300–600 new papers/day → score title+abstract against rubric + interests → ~30.
2. **Enrich:** venue/peer-review status, affiliations, Semantic Scholar author record, HF upvotes, code/weights, T2 mentions → top `max_papers_deep` (default 6) + `max_briefs`.
3. **Full read** (`paper-analyst`, Opus): arXiv HTML first, PDF fallback; reviewer-grade reading, not abstract paraphrase.
4. **Paper brief** (§8.3) → deep-dive.

### 8.3 Paper brief fields
One-line TL;DR · plain-language explanation · problem · key idea · method steps (→ diagram) · results vs baselines (each number with table/figure ref → chart) · **critical review** (limitations, eval contamination risk, sample size, compute cost, cherry-picking concerns) · reproducibility (code, data, weights, license) · practical takeaway (who should care, what to try) · **reading guide** (sections to read, glossary, reading time, difficulty) · real figures (captioned, credited; hotlinked to source, copied only if arXiv license is CC BY/CC0) · related/prior work (Semantic Scholar) and prior Pulse coverage links.

### 8.4 Layout
Paper of the day (feature) → Top papers (deep-dives) → Also notable (briefs) → Long reads → Venue watch.

## 9. Report template & visual system

### 9.1 Fixed frame (not model-editable)
Masthead (edition, date/window, headline, Pulse score vs 7-day avg, theme toggle) → KPI tiles → TL;DR → generative front-page dashboard → adoption radar → four sections (filter row: section, type, min impact, confidence, new vs update; Expand all / Collapse all) → action list → signals box → corrections → methodology & source-health footer.

Items are native `<details>/<summary>` (works without JS, prints expanded), with stable permalinks (`#<item-id>`). Section colors fixed (Cove categorical order: models=blue, tooling=orange, research=aqua, oss=yellow); status colors reserved for confidence/severity, always with label.

### 9.2 Generative visual blocks (model-authored, token-themed)

| Block | Spec format | Notes |
|---|---|---|
| Chart | **Vega-Lite** JSON | Schema-validated; Pulse theme applied by renderer (light + dark); `vega-embed` tooltips; static SVG/PNG via `vl-convert` for Markdown/notifications |
| Dashboard | Layout DSL (grid of tiles/charts/tables) | Daily front page; ad-hoc panels |
| Diagram | Mermaid, or SVG restricted to theme color classes | Paper methods, architectures, flows |
| Image | Real only: arXiv HTML figures, Playwright screenshots, OG images | Caption, credit, alt, license required |
| Motion | Animated SVG/CSS (respects `prefers-reduced-motion`); GIF via Playwright + gifski | Agent-loop animations, UI demos, notification teaser |
| Custom HTML | Sandboxed iframe, no network, size-capped, tokens only | Last resort; strictest lint |

Every visual requires: title (sentence case), alt text, source note, and a data-table view for charts. Visual budget: ≥`visuals.min_per_deep_dive` per deep-dive; fresh front-page dashboard daily.

### 9.3 Design rules and enforcement
- **`pulse-design` skill** teaches: choose the form first (is it even a chart?), color by job (categorical/sequential/diverging/status), one y-axis, ≤8 series (fold to "Other"), direct labels for ≤4 series, thin marks, recessive grid, diagram complexity limits, image and motion rules, accessibility; includes good/bad examples. Derived from the `dataviz` and diagramming principles plus Anthropic's `frontend-design` skill.
- **Gates (in order):** (1) schema validation (Vega-Lite, layout DSL, Mermaid parse, SVG allowlist sanitizer); (2) **design lint** (tokens only, no dual axis, required title/alt/source, min 11px text, sentence case); (3) palette validator (CVD separation, contrast) for any non-default colors and for custom themes; (4) **design-reviewer** vision rubric on light/dark/mobile screenshots → ≤2 fix rounds → fallback.

### 9.4 Themes
- Reader toggle: **Auto / Light / Dark**, persisted per viewer (localStorage, try/catch), `?theme=` URL override; charts re-theme live without reload (separately selected dark ramps, not inverted).
- `themes/<preset>/tokens.yaml` holds light + dark tokens; presets `pulse`, `paper`, `terminal`; `custom` = copy and edit. Config `theme.overrides` for accent/fonts/section colors.
- Build fails a theme that breaks contrast or section-color distinguishability.
- Notification screenshot uses `theme.default` (light when `auto`).

## 10. Sources & quality rules

### 10.1 Registry (`sources/sources.yaml` + `sources.local.yaml`)
Entry fields: `id`, `name`, `kind` (rss|api|github_releases|page|search), `url`, `tier` (T1|T1-data|T2|T3), `sections[]`, `fetch` params, `trust`, `allow_domains[]`. Daily health recorded and shown in the footer.

| Tier | Role | Examples |
|---|---|---|
| T1 primary (required per item) | Official word | Lab newsrooms/API changelogs (Anthropic, OpenAI, Google DeepMind, Meta, Mistral, DeepSeek, Qwen, xAI, NVIDIA, Microsoft); GitHub releases watchlist (claude-code, codex, gemini-cli, Cursor changelog, opencode, MCP spec + servers, Agent SDKs, LangGraph, Pydantic AI, Mastra, Vercel AI SDK, vLLM, SGLang, llama.cpp, Ollama, Transformers); official MCP registry; `anthropics/claude-plugins-official`; `anthropics/skills`; model cards |
| T1 data | Numbers | OpenRouter models API daily diff (new models, price changes), HF Daily Papers, arXiv, HF trending, GitHub search, SWE-bench, LMArena, Epoch AI, Artificial Analysis (optional key), GitHub Advisory DB, OSV, CISA KEV |
| T2 curators (signal only) | Importance | Simon Willison, Latent Space/AINews, Interconnects, Import AI, Ahead of AI, The Batch, HN front page (points threshold), Lobsters, r/LocalLLaMA |
| T3 discovery | Recall | WebSearch/WebFetch; optional Exa MCP (semantic search), Jina Reader/Firecrawl (hard pages) |
| Blocked | — | Content farms, SEO listicles, AI-generated news sites, re-post aggregators |

### 10.2 Ranking
Impact (1–5, per-section rubric), Novelty (1–5), Relevance (interests profile; never drops a major out-of-interest item), Pulse score = Σ impact of published items, compared to 7-day average.

### 10.3 Coverage memory
`state/coverage.jsonl`: one line per published item — `entity_key`, canonical URL, title, short summary, date, `thread_id`, `item_id`. `state/threads.jsonl`: story threads (e.g. rumor → launch → open weights) powering archive timelines. `state/snapshots/` keeps API snapshots needed for diffs (e.g. OpenRouter model list).

### 10.4 Reliability rules (enforced)
1. ≥1 **T1 source fetched during this run**; link checker confirms HTTP 200 and entity mention.
2. Publish date verified inside the window (feed/page metadata); undated → excluded unless official changelog.
3. Every number has `source_ref` + `quote`; verifier re-checks; mismatches dropped.
4. Confidence: Confirmed (T1) → main sections; Reported (credible T2 only) → Signals box; Rumor → excluded by default.
5. Prompt-injection hygiene: fetched content is data; research subagents have read-only tools; nothing fetched can trigger write/push/notify.
6. Recall check vs T2 curators + HN front page before finalizing.
7. Corrections: later runs that find an error add a Corrections entry and amend coverage.
8. Summaries in Claude's own words; short quotes only.

## 11. Hosts

| | Cloud routine | GitHub Actions | Local |
|---|---|---|---|
| Trigger | Routine schedule, 17:07 local (from config) | `schedule: cron` in UTC from `pulse schedule print` (default `7 14 * * *`) + `workflow_dispatch` | systemd user timer `OnCalendar=*-*-* 17:00:00 Europe/Istanbul`, `Persistent=true`; launchd plist on macOS |
| Repo | `pulse-instance` only (single repo → repo hooks load) | Workflow lives in private instance repo (avoids public-repo 60-day schedule disable) | Local clone of instance |
| Auth | Subscription | `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`) or `ANTHROPIC_API_KEY` | Subscription login or API key |
| Plugin | `.claude/settings.json` marketplace + `enabledPlugins`; fallback: setup script `claude plugin install` | Action inputs `plugin_marketplaces` + `plugins` | `claude plugin install pulse@pulseai` |
| Environment | Setup script installs uv, deps, Playwright Chromium (cached ≤5 min); network: Custom allowlist from `pulse doctor --allowlist` (or Full) | Steps install uv + Chromium; ~30–40 min/run fits free 2,000 min/month | Same CLI deps |
| Command | Prompt `/pulse:daily` | `prompt: "/pulse:daily"`, `claude_args` with model, max turns | `claude -p "/pulse:daily" --permission-prompts none --allowedTools <list> [--max-budget-usd N]` |
| Secrets | Env vars on environment (`PULSE_NOTIFY_URLS`, optional API keys) / network secrets where header-based | Repo secrets | `~/.config/pulse/env` (0600) |

**Guardrail hooks** (plugin `hooks/hooks.json`): during research phases deny `git push`, notifier calls, and writes outside `runs/`; Stop hook verifies a checkpoint/report exists and that `pulse validate` passed. Correctness must not depend solely on hooks — the CLI gates enforce the same rules.

Local Claude Code must be ≥ the version that supports the flags used (`--permission-prompts` ≥2.1.259; current latest 2.1.296; the author's machine is on 2.1.220 → docs include an upgrade step and `pulse doctor` checks the version).

## 12. Storage, site, notifications

- **Storage:** `reports/YYYY/MM/DD/` with single-file `index.html` (inline CSS/JS, works offline and as an attachment), `report.json`, `report.md`, `assets/` (chart SVG/PNG, screenshots, GIFs).
- **Site:** archive calendar heatmap (Pulse score per day), Pagefind full-text search, entity/thread pages ("everything about Claude Code"), 30-day trends dashboard, System health page.
- **Private viewing:** Cloudflare Pages connected to the private instance repo, protected by Cloudflare Access (email OTP; free ≤50 users). Deploys on push — no deploy token inside runs. GitHub Pages documented for public instances (note: Pages from a private repo is still publicly reachable on non-Enterprise plans).
- **Notifications:** Apprise URLs from `PULSE_NOTIFY_URLS` (`tgram://`, `mailto://`, `slack://`, `discord://`, `ntfy://`; multiple allowed). Message = headline, Pulse score, TL;DR, deep links to top 3, PNG or GIF. Failure alerts include the failed step and run link.

## 13. Failure handling

- Checkpoints per step under `runs/<date>/`; `--resume`.
- Source failure → retry with backoff → skip + mark in health table; >30% T1 failures → banner.
- Section agent failure → "Section unavailable" placeholder, report still ships.
- Validation failure after 2 fix rounds → **plain edition** (TL;DR + linked list) + alert.
- Lock in `state/lock.json` {host, started_at}; stale after `limits.run_minutes × 2`.
- Re-run same date overwrites, keeps edition number.
- Window from last success, capped at `window.max_hours`; beyond → catch-up digest.
- Limits: per-agent max turns, run wall-clock limit, `--max-budget-usd` on API billing.
- Notify is best-effort and never reverts publish.

## 14. Testing

- **Unit (pytest):** fetchers with recorded fixtures (no live network in CI), schema models, schedule tz→UTC conversion (incl. DST-observing zones), history matching (exact + entity keys), each design-lint rule, palette validator, SVG sanitizer, link checker.
- **Snapshot + visual regression:** golden HTML of example reports; Playwright screenshots light/dark/mobile vs baselines.
- **Agent evals (frozen day):** `/pulse:daily --fixtures <day>` asserting schema validity, every number traced to a quote, planted major items included (recall), planted duplicate dropped/marked update, planted prompt-injection page ignored, design-review score ≥ threshold. Packaged as `claude plugin eval` suites.
- **Public repo CI:** lint, tests, `claude plugin validate`, build examples, deploy demo site.
- **User setup:** `pulse doctor` — Claude Code version, auth, network allowlist reachability, secrets present, push permission (dry-run), notifier test message.

## 15. Observability & cost

`runs/<date>/run.json`: duration, tokens/cost per agent and model (from `--output-format json` where available), funnel (scanned → triaged → verified → published), source health, lint results, design-review scores, recall-check misses. Feeds the System health page. Subscription hosts draw plan usage; API hosts capped by `limits.max_budget_usd`. Real cost to be measured in the first dry runs and documented.

## 16. Security & privacy

- Public engine contains no personal data or secrets; instance repo is private.
- Secrets only in host secret stores/env files; never committed; `pulse doctor` scans for accidental secrets in the instance repo.
- Fetched content treated as untrusted data (rule 10.4.5); custom HTML visuals sandboxed with no network.
- Routine/Actions push only to the configured instance repo/branch.

## 17. Risks and open questions (first spikes in the plan)

1. **Plugin auto-install in cloud routine sessions** via project `.claude/settings.json` — verify; fallback: setup-script install.
2. **Routine push to `main`** of the instance repo (default `claude/` branch prefix unless prompt directs otherwise) — verify; fallback: push to `claude/reports` + auto-merge workflow, or Cloudflare deploys from that branch.
3. **Cloud network allowlist** coverage for all registry domains and whether WebFetch is subject to it — verify; fallback: Full network access documented.
4. **Run duration/cost** on Opus for editor + analyst + verifier — measure; tune models_by_role.
5. **Source API terms/rate limits** (Semantic Scholar, OpenReview, alphaXiv, Reddit) — verify per source; mark optional where keys are needed.
6. **Figure licensing** — rely on arXiv license metadata; default hotlink with credit.

## 18. Delivery milestones (for the implementation plan)

- **M0 Spikes:** risks 1–3 on a throwaway instance.
- **M1 Engine core:** config, schema, history store, CLI skeleton, fetchers (T1 + data), render frame + themes + theme switch, local host adapter. Produces a report from fixtures.
- **M2 Agents & skills:** `/pulse:daily` orchestrator, section researchers, verifier, coverage logic, guardrail hooks.
- **M3 Visual system:** Vega-Lite theme + renderer, layout DSL, Mermaid/SVG, images, motion/GIF, design lint, palette validator, design-reviewer loop.
- **M4 Research desk:** arXiv/OpenReview/S2/OpenAlex/HF fetchers, triage, paper-analyst, paper brief template, long reads.
- **M5 Publish & notify:** publish, site (archive, Pagefind, entity pages, trends, health), Apprise, Cloudflare docs.
- **M6 Hosts & onboarding:** routine + Actions adapters, `pulse init`, `pulse doctor`, quickstarts, examples, public demo site, evals in CI.

## 19. References consulted (2026-10-11)

- Claude Code routines: https://code.claude.com/docs/en/routines
- Claude Code GitHub Actions: https://code.claude.com/docs/en/github-actions
- Headless / Agent SDK CLI: https://code.claude.com/docs/en/headless
- Cloud environments: https://code.claude.com/docs/en/cloud-environments
- Desktop scheduled tasks: https://code.claude.com/docs/en/desktop-scheduled-tasks
- Changelog (2.1.288–2.1.296): https://code.claude.com/docs/en/changelog
- Official plugins: https://github.com/anthropics/claude-plugins-official · Skills: https://github.com/anthropics/skills
- Prior art: https://github.com/kippapollo/ai-news · https://github.com/abdooay/ai-news-digest · https://github.com/rogeriomoura/ai-daily-digest · https://github.com/srijit316/daily_research_digest · https://github.com/frankzch/ai-news-brief
- Research MCP comparisons: https://parallel.ai/articles/best-web-search-mcp · https://cookiesforai.app/best/mcp-servers-for-web-research
- Apprise: https://github.com/caronc/apprise
