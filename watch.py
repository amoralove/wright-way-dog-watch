#!/usr/bin/env python3
"""Watch rescue shelters' adoptable dogs and notify on new arrivals."""
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

DIR = Path(__file__).resolve().parent
STATE = DIR / "seen.json"
LOG = DIR / "new_dogs.log"

PET_RE = re.compile(
    r'animalID=(\d+)">.*?pet-name">([^<]*)<.*?pet-age">([^<]*)<.*?pet-breed">([^<]*)<',
    re.S,
)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def fetch_wright_way(shelter):
    base = "https://adopt.wright-wayrescue.org/pet.php?animalID="
    dogs = {}
    for aid, name, age, breed in PET_RE.findall(get(shelter["page"])):
        dogs[aid] = {
            "name": html.unescape(name).strip(),
            "age": html.unescape(age).strip(),
            "breed": html.unescape(breed).strip(),
            "url": base + aid,
        }
    return dogs


def page_text(url):
    """Visible text of a page, whitespace collapsed (for reading fee schedules)."""
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", get(url), flags=re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", t)).split())


def wright_way_fees():
    """Wright-Way lists fees site-wide, not per dog."""
    text = page_text("https://wright-wayrescue.org/adoption-program-and-process")
    fees = {}
    for label, pat in (("Adult dog", r"Adult Dog:\s*\$(\d+)"), ("Puppy", r"PUPPY:\s*\$(\d+)")):
        m = re.search(pat, text, re.I)
        if m:
            fees[label] = f"${m.group(1)}"
    m = re.search(r"\$(\d+) for dogs", page_text("https://wright-wayrescue.org/seniors"))
    if m:
        fees["Senior adopters"] = f"${m.group(1)}"
    return fees


def wright_way_fee(dog, fees):
    """Puppy rate is for dogs 9 months and younger."""
    months = age_in_months(dog["age"])
    if months is None:
        return ""
    return fees.get("Puppy" if months <= 9 else "Adult dog", "")


def age_in_months(age):
    """'3 weeks' / '5 months' / '1 year, 9 months' -> months, or None."""
    parts = re.findall(r"(\d+)\s*(week|month|year)", age, re.I)
    if not parts:
        return None
    per = {"week": 0.25, "month": 1, "year": 12}
    return sum(int(n) * per[u.lower()] for n, u in parts)


def age_from_months(months):
    """Turn an age in months into '3 months' / '2 years'."""
    if months < 12:
        n, unit = months, "month"
    else:
        n, unit = months // 12, "year"
    return f"{n} {unit}{'s' if n != 1 else ''}"


def age_from_birthday(ts):
    """Turn a Unix-timestamp birthday into '3 months' / '2 years'."""
    try:
        days = (datetime.now() - datetime.fromtimestamp(int(ts))).days
    except (TypeError, ValueError):
        return ""
    return age_from_months(max(days * 12 // 365, 0))


def fetch_shelterluv(shelter):
    """Shelters that embed ShelterLuv's adoptable-pets widget (needs the GID)."""
    url = f"https://www.shelterluv.com/api/v3/available-animals/{shelter['gid']}"
    dogs = {}
    for a in json.loads(get(url)).get("animals", []):
        if a.get("species") != "Dog":
            continue
        breed = a.get("breed") or ""
        if a.get("secondary_breed"):
            breed = f"{breed} / {a['secondary_breed']}"
        dogs[a["uniqueId"]] = {
            "name": (a.get("name") or "").strip(),
            "age": age_from_birthday(a.get("birthday")),
            "breed": breed.strip(),
            "url": a.get("public_url") or shelter["page"],
        }
    return dogs


def shelterluv_details(dog):
    """The adoption fee is only on each animal's ShelterLuv page."""
    m = re.search(r'"adoptionFee":"([^"]*)"', html.unescape(get(dog["url"])))
    if m and m.group(1):
        dog["fee"] = m.group(1).replace(".00", "")


ONETAIL_RE = re.compile(
    r'single-profile" data-name="([^"]*)" data-attributes="([^"]*)">.*?animal_id=(\d+)',
    re.S,
)
STAT_RE = re.compile(
    r"stats-header'>\s*([^<]*?)\s*</div>\s*<div class='stats-content'>\s*([^<]*?)\s*</div>"
)


def fetch_onetail(shelter):
    """One Tail's WordPress plugin; the list page has name, type and age in months."""
    dogs = {}
    for name, attrs, aid in ONETAIL_RE.findall(get(shelter["page"])):
        a = json.loads(urllib.parse.unquote(attrs))
        if a.get("petType") != "Dog":
            continue
        dogs[aid] = {
            "name": html.unescape(name).strip(),
            "age": age_from_months(int(a["age"])) if a.get("age") is not None else "",
            "breed": "",
            "url": f"https://www.onetail.org/animal-details?animal_id={aid}",
        }
    return dogs


def onetail_details(dog):
    """Breed (and exact age) are only on each dog's detail page."""
    stats = dict(STAT_RE.findall(get(dog["url"])))
    dog["breed"] = html.unescape(stats.get("Breed", ""))
    dog["age"] = html.unescape(stats.get("Age", "")) or dog["age"]


# "key" is used in seen.json; never change it once a shelter has been watched.
SHELTERS = [
    {
        "key": "wright-way",
        "name": "Wright-Way",
        "page": "https://adopt.wright-wayrescue.org/?speciesID=1&stageID=2",
        "fetch": fetch_wright_way,
        "fees": wright_way_fees,
        "fee_for": wright_way_fee,
        "fees_page": "https://wright-wayrescue.org/adoption-program-and-process",
    },
    {
        "key": "border-tails",
        "name": "Border Tails",
        "page": "https://www.bordertailsrescue.org/adoptable-dogs-copy",
        "gid": 45923,
        "fetch": fetch_shelterluv,
        "details": shelterluv_details,
    },
    {
        "key": "one-tail",
        "name": "One Tail",
        "page": "https://www.onetail.org/available-pets/",
        "fetch": fetch_onetail,
        "details": onetail_details,
    },
]


def notify(title, msg, click, priority="high"):
    """Push to phone via ntfy.sh (topic name in topic.txt)."""
    topic = os.environ.get("NTFY_TOPIC") or (DIR / "topic.txt").read_text().strip()
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=msg.encode("utf-8"),
        headers={"Title": title, "Tags": "dog", "Click": click, "Priority": priority},
    )
    urllib.request.urlopen(req, timeout=30).read()


def load_state():
    if not STATE.exists():
        return {}
    state = json.loads(STATE.read_text())
    # Old format was a flat {animalID: dog} map for Wright-Way only.
    if state and all("name" in v for v in state.values()):
        state = {"wright-way": state}
    return state


def check_fees(shelter, state, now):
    """Read a shelter's fee schedule and alert when it changes (e.g. a fee special)."""
    key, name = shelter["key"], shelter["name"]
    try:
        fees = shelter["fees"]()
    except Exception as e:
        print(f"{now} {name}: fee check failed: {e}", file=sys.stderr)
        return {}
    if not fees:
        # Page layout changed; keep the last known schedule.
        print(f"{now} {name}: no fees parsed; skipping", file=sys.stderr)
        return {}

    known = state.setdefault("fees", {})
    old = known.get(key)
    known[key] = fees
    STATE.write_text(json.dumps(state, indent=1))

    if old is not None and old != fees:
        changes = [
            f"{label}: {old.get(label, 'none')} -> {fees.get(label, 'none')}"
            for label in sorted(set(old) | set(fees))
            if old.get(label) != fees.get(label)
        ]
        notify(f"{name} adoption fees changed", "\n".join(changes), shelter["fees_page"])
        print(f"{now} {name}: fees changed: {'; '.join(changes)}")
    return fees


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    state = load_state()
    listed = {}

    for shelter in SHELTERS:
        key, name = shelter["key"], shelter["name"]
        fees = check_fees(shelter, state, now) if "fees" in shelter else {}
        try:
            dogs = shelter["fetch"](shelter)
        except Exception as e:
            print(f"{now} {name}: fetch failed: {e}", file=sys.stderr)
            listed[name] = f"site down ({getattr(e, 'code', None) or type(e).__name__})"
            continue
        if not dogs:
            # Page layout changed or empty response; don't clobber state.
            print(f"{now} {name}: no dogs parsed; skipping", file=sys.stderr)
            listed[name] = "no dogs found on page"
            continue
        listed[name] = len(dogs)

        first_run = key not in state
        seen = state.setdefault(key, {})
        new = {k: v for k, v in dogs.items() if k not in seen}
        if not first_run and "details" in shelter:
            for d in new.values():
                try:
                    shelter["details"](d)
                except Exception as e:
                    print(f"{now} {name}: details failed for {d['name']}: {e}", file=sys.stderr)
        for d in new.values():
            d.setdefault("fee", shelter["fee_for"](d, fees) if "fee_for" in shelter else "")
        seen.update({k: {f: v[f] for f in ("name", "age", "breed")} for k, v in dogs.items()})
        STATE.write_text(json.dumps(state, indent=1))

        if first_run:
            print(f"{now} {name}: baseline saved: {len(dogs)} dogs")
            continue

        with LOG.open("a") as f:
            for d in new.values():
                f.write(f"{now}\t{name}\t{d['name']}\t{d['age']}\t{d['breed']}\t{d['url']}\n")

        if new:
            body = "\n".join(
                f"{d['name']} - {d['age']}, {d['breed']}"
                + (f" - {d['fee']} fee" if d["fee"] else "")
                for d in new.values()
            )
            title = f"{len(new)} new dog{'s' if len(new) > 1 else ''} at {name}"
            click = next(iter(new.values()))["url"] if len(new) == 1 else shelter["page"]
            notify(title, body, click)
        print(f"{now} {name}: {len(dogs)} listed, {len(new)} new")

    if os.environ.get("HEARTBEAT") == "true":
        cutoff = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
        lines = LOG.read_text().splitlines() if LOG.exists() else []
        found = sum(1 for line in lines if line[:16] >= cutoff)
        counts = ", ".join(f"{n}: {c}" for n, c in listed.items())
        notify(
            "Still watching",
            f"Dogs listed - {counts}. {found} new in the last 24 hours.",
            SHELTERS[0]["page"],
            priority="low",
        )


if __name__ == "__main__":
    main()
