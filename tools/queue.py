#!/usr/bin/env python3
"""Upload-queue helper for Oddly Proven.

data/schedule.json is a list of items:
  {"publish_date": "2026-11-11", "time": "14:00", "type": "short"|"long", "slug": "...",
   "title": "...", "description": "...", "video": "queue/<slug>.mp4", "srt": "queue/<slug>_en.srt",
   "status": "ready"|"scheduled", "youtube_url": null}

Commands:
  queue.py due [YYYY-MM-DD]       -> JSON list of 'ready' items whose publish_date <= date (default today, America/Matamoros)
  queue.py add <json-file>        -> append items from a JSON list
  queue.py done <slug> <url>      -> mark item scheduled and store url
  queue.py pending                -> count of 'ready' items per type and the last publish_date queued
  queue.py next-date <type>       -> next free publish date for that type (shorts daily, long every 2 days)
  queue.py studio-date YYYY-MM-DD -> "11 Nov 2026" (format Studio's date field expects)
"""
import json, sys, os, datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "schedule.json")
RAW = "https://raw.githubusercontent.com/brandondelta131-cloud/oddlyproven-videos/main/"


def today():
    return datetime.datetime.now(ZoneInfo("America/Matamoros")).date()


def load():
    return json.load(open(PATH)) if os.path.exists(PATH) else []


def save(items):
    json.dump(items, open(PATH, "w"), indent=2, ensure_ascii=False)


def main():
    cmd = sys.argv[1]
    items = load()
    if cmd == "due":
        d = sys.argv[2] if len(sys.argv) > 2 else today().isoformat()
        due = [dict(i, video_url=RAW + i["video"], srt_url=RAW + i["srt"] if i.get("srt") else None)
               for i in items if i["status"] == "ready" and i["publish_date"] <= d]
        print(json.dumps(due, indent=2, ensure_ascii=False))
    elif cmd == "add":
        new = json.load(open(sys.argv[2]))
        slugs = {i["slug"] for i in items}
        items += [n for n in new if n["slug"] not in slugs]
        save(items)
        print("added", len(new))
    elif cmd == "done":
        for i in items:
            if i["slug"] == sys.argv[2]:
                i["status"] = "scheduled"; i["youtube_url"] = sys.argv[3]
        save(items)
    elif cmd == "pending":
        out = {}
        for t in ("short", "long"):
            r = [i for i in items if i["type"] == t and i["status"] == "ready"]
            allt = sorted(i["publish_date"] for i in items if i["type"] == t)
            out[t] = {"ready": len(r), "last_date": allt[-1] if allt else None}
        print(json.dumps(out))
    elif cmd == "next-date":
        t = sys.argv[2]
        step = 1 if t == "short" else 2
        dates = sorted(i["publish_date"] for i in items if i["type"] == t)
        nd = (datetime.date.fromisoformat(dates[-1]) + datetime.timedelta(days=step)) if dates else today()
        print(max(nd, today()).isoformat())
    elif cmd == "studio-date":
        print(datetime.date.fromisoformat(sys.argv[2]).strftime("%-d %b %Y"))


if __name__ == "__main__":
    main()
