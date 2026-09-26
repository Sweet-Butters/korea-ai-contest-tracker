# AI Contest Radar (AI 공모전 레이더)

**English** · [한국어](README.ko.md)

A self-updating directory of AI competitions, hackathons, idea contests and startup pitch competitions
in South Korea, plus government startup funding programmes — and a real-world test of **[TypeSafe Jev](https://typesafe.ai)**, a model that returns
typed, calibrated decisions instead of text.

**Live site:** https://sweet-butters.github.io/korea-ai-contest-tracker/

Every morning a GitHub Actions job collects listings from 11 Korean sources, keeps the AI-related
ones, asks Jev to double-check the borderline calls, merges duplicates across sites and redeploys the
site. No server, no database, no chat-LLM tokens in the daily loop.

## What the site does

- **List / by-category / calendar views.** The calendar shows deadlines, application openings and final rounds.
- **Sort** by deadline, prize money (parsed from free text like `총상금 1억 2,600만원`), newest, most-listed, Jev confidence, name.
- **Filter** by status, category, region, source, AI-only, has-prize, hide-unverified.
- Shareable URLs: `?view=calendar&sort=prize&cat=hackathon`.
- **Admin (`/admin`)**: edit the keyword rules in the browser → commits `config/keywords.json` → the workflow re-collects. Shows per-source health, Jev outcome stats and recent runs.

## Architecture

```
apps/web        Next.js + TypeScript   main site (static export)
apps/admin      Next.js + TypeScript   keyword admin, served at /admin
packages/shared TypeScript             shared types, prize parser, date helpers, theme
collector/      Python                 the "server": runs in GitHub Actions
config/         keywords.json          classification rules, editable from /admin
data/           contests.json · meta.json · jev_cache.json · jev_runs.jsonl
```

```
06:00 KST daily, or on a keyword commit  →  GitHub Actions
  collector/sources/*    fetch 11 sources (robots.txt honoured, per-host rate limit)
  collector/classify.py  keyword rules: is it a contest? is it about AI? which category?
  collector/jev.py       Jev second opinion (cached per listing)
  collector/merge.py     fuzzy de-duplication across sites, status from dates
  → commit data/*.json → build web + admin → deploy GitHub Pages
```

| Source | How |
|---|---|
| 씽굿 (ThinkGood), 올콘 (All-Con) | list JSON endpoints |
| 링커리어 (Linkareer), 요즘것들, 콘테스트코리아, 위비티 (Wevity) | server-rendered HTML |
| DACON, AIFactory | data embedded in the page (Nuxt / Next.js flight data) |
| 이벤터스 (Event-us) | public search API |
| Dev-Event | community-curated GitHub README |
| K-Startup, 스타트업레시피 | government startup funding programmes, incubation and tenancy calls (not contests) |
| 기업마당 (bizinfo) | data.go.kr open API: nationwide government support programmes, filtered to AI and 창업 |
| Naver News | official search API, for government / local / corporate press releases |

Sources whose robots.txt disallows crawling (OnOffMix, the Campuspick API, the Daker API) are not used,
and robots.txt is re-checked on every run.

## Using Jev

### Why Jev here

Deciding "is this listing an AI contest, and what kind?" is a classification problem that runs thousands
of times a day on short Korean titles. Keyword rules get most of it right but fail at the edges:
`데이터` (data) or `SW` in a title does not make a contest AI-related, and some AI contests never say "AI".
A chat LLM could judge these, but then the output has to be parsed and validated, and it costs more.
Jev answers typed questions directly — a probability for a yes/no, a distribution over choices — so the
answer goes straight into `if` statements.

### How it is wired ([`collector/jev.py`](collector/jev.py))

Each listing (title, description, source site) is sent once with three questions:

| Question | Jev type | Used for |
|---|---|---|
| `ai`: is the contest's topic or required work about AI? | `noul` (probability) | drop weak keyword matches, rescue AI contests the keywords missed |
| `contest`: is it an open call for entries? | `noul` | drop lectures, job posts and award announcements |
| `category`: hackathon / data / dev / creative / startup / … | `choice` + confidence | replace the keyword category when confident |

The keyword rules stay in charge; Jev only overrides them when it is sure, because it reads English
better than Korean:

| Situation | Rule |
|---|---|
| Jev says it is not an open contest (`contest < 0.10`) | drop |
| Rules kept it on a weak word only, and `ai < 0.15` | drop |
| Rules dropped a contest listing for lacking AI words, and `ai ≥ 0.85` | rescue |
| `category` confidence `≥ 0.6` | use Jev's category |

Answers are cached in `data/jev_cache.json` by a hash of title + description, so a daily run only sends
new listings. Every run appends its outcome counts, latency, token use and cost to
[`data/jev_runs.jsonl`](data/jev_runs.jsonl); the admin page shows the latest run.

### Results (first full run, 2026-09-22, `jev-1.13.0`)

3,728 listings that passed the contest check reached Jev.

| Outcome | Listings | |
|---|---:|---|
| Agreed with the rules: drop | 3,035 | 81.4% |
| Agreed with the rules: keep | 501 | 13.4% |
| Kept, but moved to a different category | 170 | 4.6% |
| Dropped a weak keyword match (e.g. "데이터" only) | 16 | 0.4% |
| Dropped as not an open contest | 3 | 0.1% |
| Rescued an AI contest the keywords missed | 3 | 0.1% |

- Of the 690 listings the rules kept, Jev removed 19 (2.8%) and re-categorised 170 (25% of those kept).
- ~730 input tokens per listing; at $0.042 per million input tokens (output is free), judging all 3.7k
  listings costs about **$0.11**, and a normal day with a few dozen new listings costs a fraction of a cent.
- Latency is about **2 s per request** (p50 2,054 ms, p95 2,087 ms), so the first run is parallelised
  (4 workers) and later runs are dominated by the crawl, not by Jev.

Live numbers for every run: [`data/jev_runs.jsonl`](data/jev_runs.jsonl) and the admin page.

## Setup

Add these under **Settings → Secrets and variables → Actions**. Everything is optional; missing keys
just switch that step off.

| Name | Kind | Purpose |
|---|---|---|
| `TYPESAFE_API_KEY` | Secret | Jev second opinion ([TypeSafe console](https://console.typesafe.ai/keys)). Locally, `typesafe_api_key.txt` at the repo root (git-ignored) also works. |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | Secret | Naver News search API ([developers.naver.com](https://developers.naver.com/apps/), 25,000 calls/day free). |
| `GEMINI_API_KEY` | Secret | Extract contest name/deadline from new news articles (free tier). Without it, articles become "unverified" entries. |
| `GEMINI_MODEL` | Variable | default `gemini-flash-lite-latest` |
| `DATA_GO_KR_KEY` | Secret | [data.go.kr](https://www.data.go.kr) 일반 인증키 for the 기업마당 지원사업 공고 API (free). Without it that source is skipped. |

GitHub Pages: **Settings → Pages → Source: GitHub Actions**.

To edit keywords from `/admin` you need a [fine-grained token](https://github.com/settings/personal-access-tokens/new)
for this repository with **Contents** and **Actions** read/write. It is stored only in your browser.

## Run locally

```bash
pip install -r requirements.txt
python -m collector.main             # full collection (Node.js needed for DACON)
python -m collector.main 씽굿 DACON   # selected sources only

npm install
npm run dev:web                      # main site
npm run build && node scripts/assemble.mjs _site
```

## Notes

Only summaries and links to the original notices are shown; always check the organiser's page for
dates and eligibility. Entries whose only source is `초기조사` were seeded from a manual survey on
2026-09-21/22.
