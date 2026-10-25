# Chain Secrets Studio (Telegram Mini App)

How it fits together, so it is easy to upgrade:

| Part | File | Job |
|---|---|---|
| Settings | `docs/studio/schema.json` | One list of every setting (label, options, default). The app draws its controls from it; the pipeline reads the same defaults. |
| App | `docs/studio/index.html` | New / Editor / Library screens. Reads the public repo through the GitHub API, sends actions to the bot with `Telegram.WebApp.sendData` (deflate-compressed when long). |
| Bot | `radar.py` (`app_action`, `save_job`, `studio_index`) | Turns app actions into jobs: `new`, `save`, `voice`, `retake`, `render`, `rewrite`. Writes `jobs/<id>/storyboard.json`, `status.json` and the library index `state/studio.json`. |
| Pipeline | `studio/story.py`, `studio/auto.py`, `studio/run.py`, `.github/workflows/short.yml` | Storyboard -> house voice -> animated Short. Every setting is read with `story.settings(sb)`. |

**Add a setting:** add a field to a group in `schema.json`, then use `story.settings(sb)['your_key']` where it matters
(voice: `story.voice_job`, look: top of `auto.py`, mix: `run.render`). Old jobs keep working because missing settings fall back to the defaults.

**Add a visual:** add a template function in `auto.py` (`TEMPLATES`), its fields in `schema.json` -> `visuals`, and its name in `story.VISUALS`.

**Hosting:** GitHub Pages (Settings -> Pages -> Deploy from branch -> `main` / `/docs`). The bot's 🎬 Studio button opens
`https://fadishdeed42-spec.github.io/chain_radar/studio/` (`?job=<id>` opens a Short directly).
