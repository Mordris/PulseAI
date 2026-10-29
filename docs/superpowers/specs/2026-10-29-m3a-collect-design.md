# M3a: Collect (design)

- **Date:** 2026-10-29
- **Status:** Draft for review
- **Parent spec:** [PulseAI design spec v2](2026-10-11-pulseai-daily-research-routine-design.md), §7.4, §11, §15, §16, §20
- **Owner:** @Mordris

Decisions the owner made in the 2026-10-29 brainstorm are marked **(owner)**. Choices left to Claude are marked **(Claude's call)**: they follow the engineering rules and can be challenged in review.

## 1. Intent

M1 and M2 built the frame: schemas, registries, config, CLI, and a site that renders hand-written example reports. PulseAI still has no real input. M3a gives it one: **`pulse collect` pulls everything new from every enabled source within a time window and writes clean, schema-validated results to disk.** The research agents (M4) read those results, and the reliability gates (M3b, M4) check them.

`pulse collect` is a plain CLI command. Claude is not involved, so fetching feeds costs no tokens, behaves the same on every host, and can be tested offline.

## 2. Where M3a sits

The spec's M3 is split in two **(owner)**:

| Plan | Scope |
|---|---|
| **M3a: Collect** (this document) | Generic collector, new `sitemap` kind, full default source registry, snapshots, collected-item and run-summary schemas, `pulse collect`, weekly source-health workflow |
| **M3b: Remember and verify** | Coverage history (`state/coverage.jsonl`, `threads.jsonl`), `pulse history check`, `pulse verify links`, MCP server catalog + `pulse mcp sync`, `pulse doctor --allowlist` |

## 3. Goals

1. `pulse collect` returns real, recent items from the full default registry in one command.
2. Every source is declared in YAML. There is no code per source.
3. A broken source never stops a run; it shows up in the run summary.
4. The engine's default source list stays healthy over time: a weekly workflow finds broken sources and reports them **(owner)**.
5. Every output file validates against a JSON Schema, and Python models and TS contracts are generated from it like the rest of the repo.

## 4. Non-goals

- Ranking, triage, interest filtering, de-duplication across sources, or judging importance. Those belong to the agents (M4) and history (M3b). The collector collects; it doesn't choose.
- Reading full article or paper text. The agents fetch primary sources themselves when they research an item.
- Calling MCP servers or running web searches. Registry entries with `via: mcp` or `via: search` are read by agents in M4; `pulse collect` lists them as "not collected here" and skips them.
- Coverage history and link verification (M3b).

## 5. Anti-goals (fail even if it works)

- **Per-source code.** Even one `if source.id == …` breaks rule D18.
- **Silent loss.** A source that fails, returns nothing, or changes shape without anyone noticing.
- **Hammering sites or overriding their wishes.** No ignoring `robots.txt`, rate limits, or caching headers, and no fetching more than the window needs. A site that publishes `Content-Signal: ai-input=no` (in robots.txt or a response header) is not shipped as an enabled source **(Claude's call)**.
- **Storing other people's content wholesale.** Only metadata and a short feed-provided summary are stored (spec §11.4 rule 8).
- **Trusting fetched content.** Fetched text is data. It never becomes instructions, file paths, or commands (spec §11.4 rule 5).
- **Hardcoded values.** Every timeout, limit, length, and user agent comes from config or the registry.

## 6. Owner decisions

1. **Split M3** into M3a and M3b, as above.
2. **Default sources: the full spec §11 list, each one verified.** Every entry is checked live while it is added. Sources that need a key or account ship `enabled: false` with a note saying what to set. The owner reviews the list in the PR.
3. **Feedless labs: a new `sitemap` collector kind, plus agents for the rest.** Anthropic and Mistral publish sitemaps but no RSS; the `sitemap` kind covers them. xAI and Meta AI have neither (checked 2026-10-29) and become entries that M4's agents check.
4. **GitHub releases come from the GitHub REST API** (`https://api.github.com/repos/<owner>/<repo>/releases`) through the generic `json` kind.
   - **Why the API:** the owner first chose the public `releases.atom` feeds, but `github.com/robots.txt` disallows `/*.atom$` for all user agents (checked 2026-10-29). PulseAI respects robots.txt, so the owner switched to the API, which is official and allowed for programmatic use.
   - **Data:** each release returns `tag_name`, `name`, `published_at`, `prerelease`, `draft`, `html_url` and `body`.
   - **Auth:** a token is used when `GITHUB_TOKEN` is set and is optional otherwise (§9). Unauthenticated, the API allows 60 requests an hour, which covers a watchlist of about 40 repositories fetched once a day. GitHub Actions provides `GITHUB_TOKEN` automatically.
   - **What stays with MCP:** what the API-as-a-source doesn't cover (search, trending, issue details). That arrives with the M3b catalog.
   - **Effect on D18 ("MCP-first"):** this refines it. **Anything with an allowed feed or public API goes through the collector.** The spec §7.4 example that lists `claude-code-releases` as `via: mcp` is superseded.
5. **A weekly source-health workflow** runs every default source live and keeps one GitHub issue listing what is broken.

## 7. How `pulse collect` behaves

### 7.1 Command

```
pulse collect [--instance DIR] [--section ID]... [--source ID]... [--since ISO] [--until ISO]
              [--date YYYY-MM-DD] [--out DIR] [--offline] [--format table|json]
```

- **Sources:** all enabled `via: collector` entries in the merged registry (engine defaults plus instance overrides, merged by `id` as today), narrowed by `--section` and `--source`.
- **Window:** `--since`/`--until` when given; otherwise from `until = now` back `config.window.max_hours`. M3b/M6 will compute `since` from the last successful run; M3a keeps the flags so that change needs no CLI break **(Claude's call)**. The window filters items from `rss`, `atom` and `json` sources only; snapshot and sitemap items are new by definition (§8.4, §8.5).
- **Once per daily run** **(Claude's call)**: the M4 orchestrator runs `pulse collect` once, before the section researchers start. Each researcher reads the files for its section; `collect.json` lists each source's sections. This replaces the parent spec §8 step 2 wording, where every researcher ran its own `pulse collect --section`. `--section` and `--source` stay for manual use and debugging.
- **Re-runs:**
  - A run with `--source` or `--section` updates only those sources' files and their rows in an existing `collect.json`. Rows for other sources are kept.
  - One instance lock (`<instance>/.pulse/collect.lock`, with a stale timeout of `limits.run_minutes`) stops two collects on the same instance from overlapping. The second exits 2 with a clear message.
- **Run date:** `--date` (default: today in `config.schedule.tz`) names the output folder and fills `{date}` in URL templates.
- **Output:** `<instance>/runs/<date>/collected/` unless `--out` is given.
- **`--offline`** is used by tests and evals: requests are served from recorded fixtures only, and a missing fixture is an error.
- **`--format`:** a table for people (default when stdout is a terminal), JSON for scripts.

**Exit codes** follow the existing CLI:

| Code | Meaning |
|---|---|
| 0 | Every selected source succeeded (an empty result counts as success) |
| 1 | The run finished, but at least one source failed; the summary says which |
| 2 | Nothing could run: invalid config or registry, or an unwritable output folder |

### 7.2 One source, step by step

1. **Expand the URL template** with `{date}`, `{since}`, `{until}` and `{config.*}` (spec §7.4). Unknown variables are registry-check errors, not runtime surprises.
2. **Fetch** through one shared HTTP client:
   - HTTP caching (conditional requests with ETag/Last-Modified)
   - retries with exponential backoff on network errors, 429 and 5xx (honoring `Retry-After`)
   - a per-host rate limit
   - a timeout
   - `robots.txt` checks
   - an optional auth header built from `http.auth_header`, the env var named in `http.auth_env`, and `http.auth_prefix`

   Per-source `http` settings override the defaults in config (§9).

   Rate-limit responses are treated alike: 429, and 403 with `X-RateLimit-Remaining: 0` (GitHub's form). The client waits until `Retry-After` or `X-RateLimit-Reset` when that falls within the source's retry budget; otherwise the source fails with reason `rate_limited`.
3. **Parse** according to the collector kind (§8).
4. **Map fields** to a collected item: `id`, `title`, `url`, `published`, `summary`, `signal`. JSON kinds use the registry's JMESPath expressions; feed kinds use feedparser's normalized fields.
5. **Normalize:**
   - canonical URL (courlan; drop tracking parameters)
   - an ASCII item id that is stable across runs (`<source-id>:<slug or hash of the canonical URL>`; the builder chooses the hashing)
   - timestamps converted to UTC ISO 8601
   - summary sanitized with nh3 (no markup kept), whitespace collapsed, cut to `collect.summary_max_chars`
6. **Filter by the window** (`rss`, `atom` and `json` kinds only). Items published outside `[since, until)` are dropped. An undated item is dropped, unless the source sets `changelog: true` (spec §11.4 rule 2); then it is kept and marked `undated`.
7. **Write** `collected/<source-id>.json` and add the source's outcome to the run summary.

Sources run concurrently, up to `collect.concurrency` at a time, while the per-host limit keeps any single site polite **(Claude's call)**.

### 7.3 Outputs

`runs/<date>/collected/<source-id>.json` validates against the new **`schema/collected.schema.json`**:
- **The source block:** id, name, tier, trust, sections, kind, and the URL that was fetched.
- **The window** used for the run.
- **Each item:** `id`, `source_id`, `title`, `url`, `canonical_url`, `published` (or `null` with `undated: true`), `summary`, `signal` (a number when the source declares one), and, for snapshot and sitemap kinds, `change` (§8.4, §8.5).

`runs/<date>/collected/collect.json` validates against the new **`schema/collect-run.schema.json`**:
- **Run fields:** engine version, start and finish time, window, and the options used.
- **One row per selected source** with:
  - `status`: `ok`, `empty`, `failed`, or `skipped`
  - `reason` for failed and skipped sources: `http_404`, `timeout`, `parse_error`, `robots_disallowed`, `missing_auth_env`, …
  - HTTP status, item count, items dropped by the window, duration, and whether the response came from the cache
- **Sources not collected here** (`via: mcp` / `via: search`), listed so M4 knows to handle them.

This file is what M6's health page and the report's source-health footer will read.

Python models (datamodel-code-generator) and TS contracts are generated from both schemas, and CI's drift checks cover them, as for every schema today.

## 8. Collector kinds

The four kinds in the current schema stay. One kind is new.

### 8.1 `rss` and `atom`
Parsed with feedparser. Field mapping is implicit (feedparser normalizes both formats); an optional `fields` block can pick other elements when a feed is unusual **(Claude's call)**.

### 8.2 `json`
As specified today: `items` (JMESPath to the list) plus `fields` (JMESPath per field).
- **GitHub releases** are `json` sources. The URL is `https://api.github.com/repos/<owner>/<repo>/releases?per_page=<n>`, and `items` filters out drafts.
- **Prereleases stay**, with `prerelease` mapped into the item. M4 decides whether they matter.
- **Auth:** `http.auth_env: GITHUB_TOKEN` with `http.auth_optional: true` (§9).
- **Watchlist:** all repositories from spec §11.1 (Claude Code, Codex, Gemini CLI, opencode, MCP spec and SDKs, Agent SDKs, LangGraph, Pydantic AI, Mastra, Vercel AI SDK, vLLM, SGLang, llama.cpp, Ollama, Transformers, `anthropics/claude-plugins-official`, `anthropics/skills`, …), each confirmed during verification.

### 8.3 Pagination (all JSON kinds)
None in M3a. Every default JSON source returns one page for a day's window. If verification finds one that doesn't, the builder adds a declarative `pagination` block to the schema rather than code for that source **(Claude's call)**.

### 8.4 `json-snapshot-diff`
As specified today: `items`, `key`, `track`, `fields`.

**Snapshots are stored per run date** so re-runs reproduce the same result **(Claude's call)**:
- The location is `<instance>/state/snapshots/<source-id>/<date>.json`.
- A run for `--date D` compares the new snapshot with the latest snapshot dated before D, by `key`. Running D twice gives the same diff: the second run overwrites `D.json` and compares against the same earlier file.
- `collect.snapshot_keep` (config) controls how many dated snapshots are kept per source.
- It emits one item per entry that was added or removed, or whose tracked fields changed.
  - `change` holds the kind (`added`, `removed` or `changed`) and the field paths with old and new values.
  - `detected_at` is the run time.
  - `published` comes from the entry's date field when one is mapped, and is otherwise `null`. A change is new by definition, so the window does not filter it.
- **First run:** with no earlier snapshot there is nothing to compare, so the run writes the baseline and emits nothing. The summary says `status: ok` with a note that the baseline was created.
- A snapshot is written only after its source succeeds.

### 8.5 `sitemap` (new)
For sites with no feed. Registry fields:
- `url`: the sitemap or sitemap index
- `include`: URL path prefixes or glob patterns to keep, e.g. `/news/`
- `exclude` (optional)
- `meta_fetch_limit`: the most pages read per run

Behavior:
1. Read the sitemap, following sitemap indexes and gzip.
2. Keep URLs that match `include` and not `exclude`.
3. Compare with the URL set (and each URL's `<lastmod>`) in the latest dated snapshot before the run date. Dated snapshots work the same as in §8.4. Candidates are:
   - new URLs (`change: added`)
   - known URLs whose `<lastmod>` moved forward (`change: updated`)

   Candidates are new by definition, so the window does not filter them.
4. For each candidate, up to `meta_fetch_limit`, fetch the page and read the title, publication date and description from its metadata (OpenGraph, `article:published_time`, JSON-LD, `<title>`). Trafilatura and htmldate do the reading. Candidates past the limit are listed in the summary as not read.
5. The first run records a baseline and emits nothing, the same as snapshot diffs.

Default entries: Anthropic news (`https://www.anthropic.com/sitemap.xml`, include `/news/`) and Mistral news (`https://mistral.ai/sitemap.xml`, path chosen during verification).

### 8.6 Labs with neither a feed nor a sitemap
xAI and Meta AI become `via: search` entries. The existing `SearchSource` gains an optional `pages` list: URLs an agent should fetch and read directly, such as `https://x.ai/news` **(Claude's call: this extends the existing `search` variant instead of adding a fourth `via` value)**. `pulse collect` reports them under "not collected here". M4's researcher handles them.

## 9. Configuration and registry changes

**New `collect` section in `pulse.config.yaml`** (schema-validated; engine defaults in `defaults/pulse.config.yaml`) **(Claude's call)**:
- `user_agent`: a template naming PulseAI, its version, and the repository URL
- `concurrency`
- `per_host_per_minute`
- `timeout_seconds`
- `retries`
- `summary_max_chars`
- `respect_robots` (default `true`)
- `cache_dir` (default `<instance>/.pulse/http-cache`, git-ignored)
- `snapshot_keep`

Engine defaults hold the values. No literal appears in code.

**Registry schema changes (`schema/sources.schema.json`):**
- **New collector variant `sitemapCollector`** (§8.5).
- **`changelog: boolean`** (default `false`) on collector sources, for rule 11.4.2.
- **`http.auth_optional: boolean`** (default `false`). When `true` and the named env var is unset, the request goes out without auth instead of failing with `missing_auth_env`. GitHub sources use it.
- **`fields` optional on feed kinds** (§8.1).
- **`pages`** on `SearchSpec` (§8.6).
- **`pulse registry check`:**
  - validates URL template variables
  - rejects a `sitemap` source without `include`
  - warns when two enabled sources share a URL
  - warns when an enabled source requires auth (`auth_env` without `auth_optional`) but the env var is unset in the current environment. This is a warning rather than an error, since CI won't have the keys.

## 10. Default source registry

Content follows spec §11.1 and §10.1, grouped into files by domain **(Claude's call)**:
- `sources/registry/labs.yaml`: lab newsrooms and API changelogs
- `releases.yaml`: the GitHub watchlist (REST API, §8.2)
- `research.yaml`: arXiv categories, HF Daily Papers, OpenReview and venue feeds, lab research blogs
- `data.yaml`: OpenRouter, leaderboards, advisories
- `curators.yaml`: T2 signal sources
- `longreads.yaml`: engineering blogs and expert writers

The M1 starter `core.yaml` entries move into these files.

For every entry, before it is committed:
1. Fetch it live once and confirm the kind parses and returns plausible items.
2. Check the site's terms, `robots.txt` (including any `Content-Signal`), and any published API rate limits. Record anything notable in `notes`.
3. Set `tier`, `trust`, `sections`, and `changelog` per spec §11.1.
4. Ship as `enabled: false`, with the env var or reason in `notes`:
   - sources that require an API key, such as Artificial Analysis and Semantic Scholar with a key
   - sources whose terms are unclear
   - sources whose robots.txt or content signals disallow PulseAI
5. Use T2 curators and HN for signal and recall checks (spec §11.1); they are never primary sources.

What was seen on 2026-10-29:

| Status | Sources |
|---|---|
| RSS or Atom | OpenAI news, Google AI blog, DeepMind blog, NVIDIA, Hugging Face blog, HN, Simon Willison |
| Public JSON API | GitHub releases (`*.atom` is disallowed by robots.txt) |
| Sitemap only | Anthropic, Mistral |
| Neither | xAI, Meta AI |
| Disallowed | Lobsters: robots.txt admits only named search engines and declares `Content-Signal: ai-input=no`, so it ships disabled. Reddit: also disallowed, so disabled |

The full list is settled during verification and reviewed by the owner in the PR **(owner)**.

## 11. Weekly source-health workflow (owner)

- **Trigger:** `.github/workflows/source-health.yml`, scheduled weekly plus `workflow_dispatch`.
- **Run:** `pulse collect` against the engine's default registry, as shipped: every collector source with `enabled: true`. Disabled sources aren't checked, whether a key, their terms, or robots rules turned them off **(Claude's call)**: no new schema field is needed, and CI never fetches a site that asked not to be fetched. It uses a scratch instance, a fixed recent window, and `--format json`. The job passes the workflow's automatic `GITHUB_TOKEN` so the GitHub releases list uses the authenticated rate limit. That is still not a configured secret.
- **Broken source:** `failed` (any reason other than `missing_auth_env`). `empty` counts as broken only when a source is empty two weeks running **(Claude's call)**: some sources are legitimately quiet for a week, so emptiness alone would be noisy.
- **Reporting:** the workflow keeps **one** issue, labelled `source-health`. It creates the issue when something is broken, updates its body with the current table, and closes it when everything passes. The previous run's `collect.json` is kept as a workflow artifact to support the two-week empty rule.
- **Security:** follows the repository's workflow rules: SHA-pinned actions, `permissions: {}` at the top, `issues: write` only on the job that edits the issue, no configured secrets (keyed sources ship disabled), and zizmor clean. Running it does not need any owner setup.

## 12. Failure handling

- **Source-level problems** (network, parse, 4xx/5xx after retries, robots disallow, missing auth env) mark that source `failed` with a reason. Other sources continue. Exit code 1.
- **Run-level problems** (config or registry invalid, output directory unwritable) stop before fetching. Exit code 2.
- **Bad items:** a source that returns malformed items (missing title or URL after mapping) has those items dropped and counted. The source fails only when every item is malformed.
- **Writes are atomic.** Each source file is written to a temporary name and renamed, so a crash never leaves half a file. Snapshots update only after the source succeeds.

## 13. Security

- **Fetched text is untrusted.** Summaries are sanitized to plain text with nh3. Titles and URLs are length-capped. URLs must be `http(s)`, and the stored canonical URL must be `https` or the item is dropped **(Claude's call)**.
- **Secrets:**
  - Auth values come only from env vars named in the registry.
  - They never appear in output, logs, cache keys, or exception messages.
  - The HTTP cache must not store responses to requests that carried an auth header unless the response allows it.
- **Redirects:** followed with a cap. A redirect to a different host is allowed but recorded in the summary.
- **No fetched value is ever used as a file path.** File names come from registry ids.

## 14. Testing

- **Unit tests** for each kind, field mapping, URL templates, window filtering, the changelog rule, normalization, sanitizing, snapshot diffing, sitemap diffing, summary building, and re-runs. A re-run for the same date must give the same diffs, and a `--source` re-run must keep the other sources' summary rows.
- **Recorded HTTP fixtures** (pytest-recording / VCR.py cassettes) for one representative source per kind, plus failure cases: 404, timeout, 429 with Retry-After, GitHub's 403 with `X-RateLimit-Remaining: 0`, malformed feed, robots disallow, and a redirect to another host. Tests never touch the network; CI runs with network access off for the pytest step **(Claude's call)**.
- **`--offline` end-to-end test:** `pulse collect` over a small fixture registry and checked-in cassettes. It checks every output file against its schema and the exit codes 0, 1 and 2.
- **Registry tests:** every default entry validates, ids are unique across files, every `sections` id exists, every enabled keyed source names its env var, and every `sitemap` entry has `include`.
- **Live checks** happen only in the weekly workflow and during source verification while building, never in PR CI.

## 15. OSS components

Latest stable versions as of 2026-10-29. All are permissively licensed. Renovate keeps them current once it is installed.

| Concern | Component | Version |
|---|---|---|
| HTTP client | httpx | 0.28.1 |
| HTTP caching | hishel | 1.4.0 |
| Retries | tenacity | 9.2.1 |
| Rate limiting | pyrate-limiter or aiolimiter (builder's choice) | 4.5.1 / 1.3.0 |
| Concurrency | anyio | 4.15.1 |
| Feeds | feedparser | 6.0.14 |
| JSON mapping | jmespath (already a dependency) | 1.1.0 |
| URL normalization | courlan | 1.4.0 |
| Ids | python-slugify | 9.1.3 |
| Sanitizing | nh3 | 0.3.7 |
| robots.txt | Protego | 0.7.0 |
| Sitemaps and page metadata | trafilatura (sitemaps, metadata) + htmldate | 2.3.1 / 1.11.0 |
| Logs | structlog | 26.1.0 |
| Recorded fixtures | pytest-recording (VCR.py 9.2.0) | 0.14.0 |

Rejected:
- **ultimate-sitemap-parser:** GPL-3.0 would bind an MIT engine.
- **extruct:** no release since 2024.

## 16. Left to the builder

- Module layout under `packages/cli/src/pulseai/` (a `collect/` package is expected).
- Async vs threaded fetching, as long as concurrency and per-host limits hold.
- How hishel stores its cache, and the cache key details.
- The exact item-id hash and slug rules, as long as ids are ASCII, stable across runs, and unique per source.
- Whether trafilatura fetches sitemaps itself or parses content fetched by the shared client. **Constraint:** every request must go through the shared client so caching, rate limits, robots and the user agent apply.
- Table layout of the human output.
- Splitting the plan into tasks, with the registry verification work as its own tasks.

## 17. Risks

1. **Sitemaps lag publication.** Some sites update them hours after a post. Acceptable for a daily run; M4's search sources are the backstop.
2. **Sites block non-browser user agents** (x.ai returned 403 for its sitemap). The registry marks such sources so they don't appear as surprise failures. PulseAI never fakes a browser user agent.
3. **Feed churn.** Labs redesign and feeds move. The weekly workflow exists for this.
4. **Window edge cases** around DST and the schedule's time zone. Covered by tests that use the existing schedule helpers.
