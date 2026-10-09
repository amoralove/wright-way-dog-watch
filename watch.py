#!/usr/bin/env python3
"""Watch Wright-Way Rescue's adoptable dogs page and notify on new arrivals."""
import html
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

URL = "https://adopt.wright-wayrescue.org/?speciesID=1&stageID=2"
BASE = "https://adopt.wright-wayrescue.org/pet.php?animalID="
DIR = Path(__file__).resolve().parent
STATE = DIR / "seen.json"
LOG = DIR / "new_dogs.log"

PET_RE = re.compile(
    r'animalID=(\d+)">.*?pet-name">([^<]*)<.*?pet-age">([^<]*)<.*?pet-breed">([^<]*)<',
    re.S,
)


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        page = r.read().decode("utf-8", "replace")
    dogs = {}
    for aid, name, age, breed in PET_RE.findall(page):
        dogs[aid] = {
            "name": html.unescape(name).strip(),
            "age": html.unescape(age).strip(),
            "breed": html.unescape(breed).strip(),
        }
    return dogs


def notify(title, msg, click):
    """Push to phone via ntfy.sh (topic name in topic.txt)."""
    topic = os.environ.get("NTFY_TOPIC") or (DIR / "topic.txt").read_text().strip()
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=msg.encode("utf-8"),
        headers={"Title": title, "Tags": "dog", "Click": click, "Priority": "high"},
    )
    urllib.request.urlopen(req, timeout=30).read()


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        dogs = fetch()
    except Exception as e:
        print(f"{now} fetch failed: {e}", file=sys.stderr)
        return
    if not dogs:
        # Page layout changed or empty response; don't clobber state.
        print(f"{now} no dogs parsed; skipping", file=sys.stderr)
        return

    first_run = not STATE.exists()
    seen = {} if first_run else json.loads(STATE.read_text())
    new = {k: v for k, v in dogs.items() if k not in seen}

    seen.update(dogs)
    STATE.write_text(json.dumps(seen, indent=1))

    if first_run:
        print(f"{now} baseline saved: {len(dogs)} dogs")
        return

    with LOG.open("a") as f:
        for aid, d in new.items():
            f.write(f"{now}\t{d['name']}\t{d['age']}\t{d['breed']}\t{BASE}{aid}\n")

    if new:
        body = "\n".join(
            f"{d['name']} - {d['age']}, {d['breed']}" for d in new.values()
        )
        title = f"{len(new)} new dog{'s' if len(new) > 1 else ''} at Wright-Way"
        click = BASE + next(iter(new)) if len(new) == 1 else URL
        notify(title, body, click)
    print(f"{now} {len(dogs)} listed, {len(new)} new")


if __name__ == "__main__":
    main()
