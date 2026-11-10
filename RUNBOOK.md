# Oddly Proven — automation runbook

Channel: **OddlyProvenFacts** (@OddlyProvenFacts), YouTube Studio channel id `UCEKPFdLZqqRkUAOe8-7Vt0A`.
Format: one Short per day (publishes 14:00 America/Matamoros) + one long video every 2 days (publishes 14:30).
Every fact must be true and sourced (source URL in the description). English narration (AI voice), big English
captions burned in, NO Spanish on screen (YouTube auto-translates). Always tick "altered or synthetic content".

## Repo layout
- `engine3d/` — premium 3D hologram engine (three.js + headless Chrome). `node engine3d/render.js <spec.json> <day> <out_dir> [--format short|long]`. See engine3d/README.md.
- `engine/shorts`, `engine/long` — older 2D engines (fallback only).
- `data/schedule.json` — upload queue (see `tools/queue.py` docstring). `data/*_shorts.json` — published scripts (avoid repeating facts).
- `queue/` — rendered videos + `_en.srt` waiting to be uploaded (served to Studio from raw.githubusercontent.com).
- `tools/studio_*.js` — browser scripts for the upload flow.

## Setup in a fresh cloud session
```
git clone https://github.com/brandondelta131-cloud/oddlyproven-videos /home/claude/oddlyproven-videos
cd /home/claude/oddlyproven-videos && bash setup.sh && export KOKORO_DIR=/tmp/kokoro
(cd engine3d && npm install --silent)
```

## PRODUCTION job (cloud only, no computer needed)
1. `python3 tools/queue.py pending`. Keep at least 3 ready Shorts and 1 ready long video ahead.
2. For each missing Short: research a jaw-dropping fact (WebSearch/WebFetch, authoritative sources, never repeat a fact in data/*_shorts.json or schedule.json, no myths/gore/real people/brands), write the spec in the same schema as data/week1_shorts.json (110–130 words, hook ≤10 words, title ≤60 chars, ≤1 emoji, hashtags incl #shorts, description = 2 lines + "Source: <url>"), render with engine3d `--format short`, QA (ffprobe + look at 3 frames with Read), copy mp4 + _en.srt to queue/, add to schedule with `publish_date = queue.py next-date short`, time 14:00.
3. Long video every 2 days (`queue.py next-date long`, time 14:30): 8–12 min, 16:9, built from 12–20 related verified facts on one theme (e.g. "25 Facts About Your Body That Sound Fake"), chapters in the description, sources list, `--format long`. Keep the MP4 under 95 MB (GitHub limit 100 MB): re-encode with ffmpeg `-crf 28 -preset veryfast` or lower bitrate if needed. Also make a 1280x720 thumbnail PNG and store it in queue/.
4. Append scripts to `data/published_specs.json` (list) so future runs don't repeat facts.
5. Every Sunday: squash git history to keep the repo small: `git checkout --orphan tmp && git add -A && git commit -m snapshot && git branch -D main && git branch -m main && git push -f origin main`.
6. Commit + push.

## PUBLISH job (needs the user's Windows computer with the Claude desktop app open, 13:30–14:30)
Uses the built-in browser (`mcp__remote-devices__Claude_Browser__*`), already signed in to the channel. Studio upload defaults already set (Education, English).
For each item from `python3 tools/queue.py due` (today and any missed days; for a missed day, schedule at the next free slot today 14:00/14:30 or publish now if the slot passed):
1. `navigate` → `https://studio.youtube.com/channel/UCEKPFdLZqqRkUAOe8-7Vt0A/videos/upload?d=ud`. Set viewport once: `resize_window` width 1400 height 1000.
2. `javascript_tool`: tools/studio_details.js with __VIDEO_URL__, __TITLE_JSON__, __DESC_JSON__ replaced (JSON-encode strings). Check the returned JSON (title, notKids=true, altered=true).
3. `javascript_tool`: tools/studio_subtitles.js with __SRT_URL__ → expect subtitles=true.
4. Long videos only: Details step → thumbnail: inject the PNG into the thumbnail file input the same way (DataTransfer from raw URL). Shorts: skip (YouTube picks the frame).
5. `javascript_tool`: tools/studio_schedule_open.js → date field focused. Then REAL keys with the browser `computer` tool: `key ctrl+a`, `type "<queue.py studio-date YYYY-MM-DD>"` (e.g. "11 Nov 2026"), `key Return`.
6. `javascript_tool`: tools/studio_time_focus.js → then real keys: `key ctrl+a`, `type "14:00"`, `key Return`.
7. `javascript_tool`: tools/studio_finish.js with __DATE__/__TIME__ → returns "Video scheduled … https://youtube.com/shorts/…". Time zone is GMT-6 local (verified).
8. `python3 tools/queue.py done <slug> <url>`; `git rm` the mp4 from queue/ (keep the .srt), commit + push.
9. Reset viewport (`resize_window` preset desktop). Send a push notification: what was scheduled + link.
If the computer is unreachable: do nothing destructive, leave items 'ready' (next run uploads them), notify the user.
