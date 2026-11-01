# Mission copilot API (owner: Baldwin)

`POST /api/copilot` (schema 2.9 in `CLAUDE.md`), a Vercel Python function in `api/copilot.py`.

```json
// request
{"question": "Which site gives the most usable days in June?", "site": "malapert_massif"}
// response
{"answer": "...", "facts_used": [{"label": "Mons Mouton usable days, best 2027-06 landing", "value": "8"}]}
```

`site` is optional (the site the user is looking at). Errors come back as `{"error": "..."}` with status
400 (bad request), 429 (more than 10 questions a minute from one address, or the AI service is busy),
502 (AI service error) or 503 (no API key configured).

## How it stays grounded

1. **Tools, not memory.** Claude (`claude-opus-5-5`, low effort, server-side refusal fallback on) gets six
   tools, each plain Python reading the computed files in `shared/`:

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
   the verified facts instead of the answer.
4. **facts_used** lists the facts whose values appear in the answer, so the chat can show its sources.

## Deploying (Dhiran's Vercel project, repo root)

- Add the environment variable **`ANTHROPIC_API_KEY`** in Vercel (Settings, Environment Variables). Never in code.
- `requirements.txt` at the repo root lists only `anthropic`. Keep web frameworks out of it, or Vercel will treat
  the whole project as a Python app and stop serving the website.
- `vercel.json` sets a 60 s limit and leaves the web app, the data pipeline and the 41 MB of grids out of the
  function bundle; the copilot only reads `sites`, `scores`, `timeline_*` and `windows_*`.

## Testing

The test lives in `data/tests/`, not here: Vercel turns every `.py` file under `api/` into an endpoint.

```bash
python -m pytest data/tests/test_copilot.py   # tools on real data, request checks, loop with a fake Claude (no key needed)
```

The fake-Claude tests check that a grounded answer comes back with its facts, and that an invented number
("99.5 usable days") is caught, sent back for a rewrite, and never returned.
