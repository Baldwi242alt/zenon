# Mission copilot API (owner: Baldwin)

`POST /api/copilot` (schema 2.9 in `CLAUDE.md`), a Vercel Python function in `api/copilot.py`.

```json
// request
{"question": "Which site gives the most usable days in June?", "site": "malapert_massif"}
// response
{"answer": "...", "facts_used": [{"label": "Mons Mouton usable days, best 2027-06 landing", "value": "8"}]}
```

`site` is optional (the site the user is looking at). Errors come back as `{"error": "..."}` with status
400 (bad request) or 429 (more than 10 questions a minute from one address).

## Three engines, all free to run

| Order | Engine | When it's used | Cost |
| --- | --- | --- | --- |
| 1 | **Gemini**: `gemini-3.5-flash-lite`, then `gemini-3.5-flash` (override with `GEMINI_MODEL`) | `GEMINI_API_KEY` is set | Free tier (daily limits per Google project, see below) |
| 2 | Claude (`claude-opus-5-5`) | only if someone sets `ANTHROPIC_API_KEY` | Paid; optional, not needed |
| 3 | **Fact finder** (no AI) | no key, the free limit is used up, the AI is unreachable, or an AI answer fails the numbers guard twice | Free, no limits |

The fact finder reads the question for site names ("Malapert", "Nobile Rim 1"...), months, budgets
("$50 million") and keywords (best/compare, when/land, dark/sun/Earth, slip/delay), calls the same tools
and fills in sentences with their numbers. It understands questions like:
- "Which site is best in June?"
- "When should we land at Malapert in March?"
- "How dark does Haworth get in August?"
- "What does a 2-day slip cost at Mons Mouton with a $50 million budget?"
Anything else gets a polite answer with these suggestions. So the copilot never breaks during a demo.

**Free-tier reality (tested Nov 11, 2026):** `gemini-3.5-flash` (served as 3.6-flash) allows only
**20 requests a day** on the free tier, and each copilot question uses 2-4 requests; `gemini-3.8-flash` was
refused as busy or hung. `gemini-3.5-flash-lite` answered reliably, so it goes first. Each request gets 12 s
and each question 25 s; after that the fact finder answers, so a slow free tier never leaves a spinner on
screen. For the demo, treat the fact finder as the dependable path and Gemini as a bonus for free-form
questions. Live answers seen: "When should we land at Malapert in March?" (Gemini, 15 s) and a polite refusal
for "What will the weather be in Paris tomorrow?".

**Briefs:** `build_scores.py` can write the 9 briefs with Gemini (`GEMINI_API_KEY` set), but the template
briefs are kept: Flash-Lite's briefs passed the numbers guard yet misread the 18 h survivable limit as
"the main risk", which would confuse a reader.

## How it stays grounded

1. **Tools, not memory.** The AI (Gemini, or Claude if configured) gets six tools, each plain Python reading the computed files in `shared/`:

   | Tool | Answers |
   | --- | --- |
   | `list_sites` | Which sites exist, where, current rank |
   | `get_site_summary(site)` | The site's score, best landing, 2027 sunlit and Earth-visible share |
   | `find_windows(site, month, min_usable_days)` | Landing times in a month meeting a usable-day bar |
   | `compare_sites(month, site_list)` | Best landing per site in a month, ranked |
   | `timeline_stats(site, start_date, end_date)` | Sunlit %, Earth %, longest dark spell and contact gap, DSN share |
   | `slip_cost(site, landing, budget)` | Usable days and cost per usable day for 0/1/2/3/7-day slips |

   Tool schemas use `strict: true`, so arguments always match.
2. **Facts.** Every tool returns labelled facts alongside its data.
3. **Numbers guard.** Every number in the answer must appear in what the tools returned (normal rounding
   allowed). If one doesn't, Claude is told which and gets one rewrite; if it still fails, the copilot returns
   the fact finder's answer instead.
4. **facts_used** lists the facts whose values appear in the answer, so the chat can show its sources.

## Deploying (Vercel, repo root)

- Get a free Gemini key at https://aistudio.google.com (Get API key, no card needed) and add it in Vercel:
  **Settings, Environment Variables**, name `GEMINI_API_KEY`, then **Redeploy**. Never put it in code.
  Without it the copilot still works, using the fact finder.
- `requirements.txt` at the repo root lists only `google-genai` and `anthropic`. Keep web frameworks out of
  it, or Vercel will treat the whole project as a Python app and stop serving the website.
- `vercel.json` sets a 60 s limit and leaves the web app, the data pipeline and the 41 MB of grids out of the
  function bundle; the copilot only reads `sites`, `scores`, `timeline_*` and `windows_*`.
- Free-tier note: Google may use what is sent on the free tier to improve its products. Everything the
  copilot sends is public NASA-derived data and the user's question; don't type private information into it.

## Testing

The test lives in `data/tests/`, not here: Vercel turns every `.py` file under `api/` into an endpoint.

```bash
python -m pytest data/tests/test_copilot.py   # tools on real data, request checks, loop with a fake Claude (no key needed)
```

Fake-Gemini and fake-Claude tests check that a grounded answer comes back with its facts, that an invented
number ("99.5 usable days") is caught and never returned, and that a used-up free limit (HTTP 429) falls back
to the fact finder. Fact-finder tests check its answers against the tools, budget reading ("2-day" is not a
budget) and whole-word site matching ("Slater" doesn't trigger "late").
