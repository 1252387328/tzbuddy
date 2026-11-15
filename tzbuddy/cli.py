"""tzbuddy command line."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from . import __version__
from .core import best_compromise, day_shift, meeting_slots, offset_str, parse_when, resolve

DEFAULT = ["local", "UTC"]


def _zones(names):
    return [resolve(n) for n in (names or DEFAULT)]


def cmd_now(a):
    zs = _zones(a.zones)
    ref = parse_when(None, zs[0][1])
    return _table(zs, ref, a.json)


def cmd_at(a):
    src_label, src = resolve(a.source)
    when = parse_when(a.time, src)
    zs = [(src_label, src)] + _zones(a.zones or ["local", "UTC"])
    seen, uniq = set(), []
    for lbl, z in zs:
        if lbl not in seen:
            seen.add(lbl)
            uniq.append((lbl, z))
    return _table(uniq, when, a.json)


def _table(zs, ref, as_json):
    rows = []
    for label, z in zs:
        t = ref.astimezone(z)
        rows.append({"zone": label, "time": t.strftime("%H:%M"), "date": t.strftime("%a %Y-%m-%d"),
                     "offset": offset_str(t), "shift": day_shift(t, ref), "iso": t.isoformat()})
    if as_json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    w = max(len(r["zone"]) for r in rows)
    for r in rows:
        h = int(r["time"][:2])
        mark = "☀" if 8 <= h < 18 else ("◐" if 6 <= h < 8 or 18 <= h < 22 else "☾")
        print(f"{r['zone']:<{w}}  {r['time']}  {mark}  {r['date']}  {r['offset']}  {r['shift']}".rstrip())
    return 0


def cmd_meet(a):
    zs = _zones(a.zones)
    tzs = [z for _, z in zs]
    day = parse_when(a.date + " 00:00" if a.date else "today", tzs[0]).date() if a.date else date.today()
    slots = meeting_slots(tzs, day, a.start, a.end, a.step, a.duration)
    if a.json:
        print(json.dumps({"date": day.isoformat(), "slots": [
            {lbl: s.astimezone(z).isoformat() for lbl, z in zs} for s in slots]}, indent=2, ensure_ascii=False))
        return 0 if slots else 1
    labels = [lbl for lbl, _ in zs]
    w = max(7, *(len(l) for l in labels))
    print("  ".join(f"{l:<{w}}" for l in labels))
    if not slots:
        t, pain = best_compromise(tzs, day, a.start, a.end)
        print(f"no {a.duration}-minute slot fits {a.start}:00–{a.end}:00 for everyone on {day}.")
        print("least painful hour:")
        print("  ".join(f"{t.astimezone(z).strftime('%H:%M'):<{w}}" for z in tzs) + f"  ({pain}h outside hours)")
        return 1
    for s in slots:
        print("  ".join(f"{(s.astimezone(z).strftime('%H:%M') + ' ' + day_shift(s.astimezone(z), s)).strip():<{w}}"
                        for z in tzs))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="tzbuddy", description="Time zones for humans.")
    p.add_argument("--version", action="version", version=f"tzbuddy {__version__}")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("now", help="current time in several zones")
    s.add_argument("zones", nargs="*")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_now)

    s = sub.add_parser("at", help='convert a time: tzbuddy at "3pm" tokyo london nyc')
    s.add_argument("time")
    s.add_argument("source", help="zone the time is in")
    s.add_argument("zones", nargs="*", help="zones to convert to (default: local UTC)")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_at)

    s = sub.add_parser("meet", help="find meeting slots inside everyone's working hours")
    s.add_argument("zones", nargs="+")
    s.add_argument("--date", help="YYYY-MM-DD (default today)")
    s.add_argument("--start", type=int, default=9, help="working day start hour (default 9)")
    s.add_argument("--end", type=int, default=18, help="working day end hour (default 18)")
    s.add_argument("--duration", type=int, default=60, help="minutes (default 60)")
    s.add_argument("--step", type=int, default=30, help="slot granularity in minutes (default 30)")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_meet)

    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("now", "at", "meet", "-h", "--help", "--version"):
        argv = ["now", *argv]
    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except ValueError as e:
        print(f"tzbuddy: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
