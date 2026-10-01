#!/usr/bin/env python3
"""Read-only structural checks for Act 2, Session 3.

This catches pacing, negotiation, fail-forward, encounter, map, and continuity
regressions. It never opens Steam or changes campaign data.
"""

from pathlib import Path
from urllib.parse import unquote
import re
import struct
import session3_cipher as cipher


ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT / "Campaign/Act 2/Session 3.md"
MAP = ROOT / "Campaign/Assets/Maps/third-ledger-lift-yard.png"


def main() -> None:
    text = SESSION.read_text(encoding="utf-8")
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    slots = re.findall(r"^\| (\d+):(\d+)–(\d+):(\d+) \|", text, re.M)
    times = [
        (int(h1) * 60 + int(m1), int(h2) * 60 + int(m2))
        for h1, m1, h2, m2 in slots
    ]
    check(
        [end - start for start, end in times] == [20, 10, 45, 10, 35, 15, 15],
        "Expected 135 planned minutes and a protected 15-minute buffer",
    )
    check(bool(times) and times[0][0] == 0 and times[-1][1] == 150,
          "Schedule must cover exactly 150 minutes")
    check(all(a[1] == b[0] for a, b in zip(times, times[1:])),
          "Schedule contains a gap or overlap")
    check(len(re.findall(r"^## Scene \d", text, re.M)) == 6,
          "Expected six numbered scenes")

    negotiation = text.split("## Scene 1 —", 1)[1].split("## Scene 2 —", 1)[0]
    for phrase in [
        "Interest 2, Patience 3, Impression 3",
        "**Protection**",
        "**Power**",
        "**Greed**",
        "**Justice**",
        "A successful Lie argument",
        "Obvious injury or continued violence",
        "At minute 20",
    ]:
        check(phrase in negotiation, f"Negotiation is missing: {phrase}")
    check("he still tells all" in negotiation and "undisclosed core facts" in negotiation,
          "Negotiation must fail forward to every required fact")
    check("Interest 3+ with no obvious injury" in negotiation,
          "Live-bait threshold must remain explicit")

    for phrase in [
        "Your work letters remain valid",
        "Reginald Veros dismissed me",
        "I want to work with you",
        "Melvin inspects the named yard",
        "at most two",
        "24-hour uninterrupted respite",
        "Cistern Steps",
        "clear water follows",
    ]:
        check(phrase in text, f"Missing continuity or closure beat: {phrase}")
    check("Reginald Veros" not in text or "Veros" in text,
          "Established superior name must remain Veros")

    for obsolete in [
        "Bellafonte is **Composed**",
        "Bellafonte is **Broken**",
        "Composed Bellafonte",
        "Broken Bellafonte",
        "Do not run the Draw Steel synchronization script",
    ]:
        check(obsolete not in text, f"Obsolete instruction remains: {obsolete}")

    rows = re.findall(
        r"^\| Four level-(\d) heroes.*?\| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$",
        text,
        re.M,
    )
    check(len(rows) >= 1, "Could not parse baseline combat budget")
    budget_rows = re.findall(
        r"^\| (?:Four level-[^|]+|Effective ES about \d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$",
        text,
        re.M,
    )
    check(len(budget_rows) == 4, "Expected four combat scaling rows")
    for captain, enforcers, yardhands, ev, creatures in budget_rows:
        c, e, y, total, count = map(int, (captain, enforcers, yardhands, ev, creatures))
        check(y % 4 == 0, f"Yardhands must be bought in squads of four: {budget_rows}")
        check(total == c * 20 + e * 10 + (y // 4) * 5,
              f"EV arithmetic error in row {(c, e, y, total, count)}")
        check(count == c + e + y,
              f"Creature count error in row {(c, e, y, total, count)}")
    check("three hostile profiles" in text.lower() and
          len(re.findall(r"^#### .+? — level \d+ .+?, EV \d+", text, re.M)) == 3,
          "Expected exactly three complete hostile profiles")
    for phrase in [
        "End of round 4",
        "Do not run round 5",
        "No creature exceeds level 4",
        "No hidden reinforcements",
        "never before the end of round 3",
        "two visible main actions",
        "Roll 1d10",
        "exact legal starting square",
        "Aid Attack cannot improve a Grab",
    ]:
        check(phrase.lower() in text.lower(), f"Missing encounter safeguard: {phrase}")

    outcome_section = text.split("### What is in hand?", 1)[1].split(
        "### Melvin's first independent case", 1
    )[0]
    for outcome in [
        "Fenwick and satchel secured",
        "Fenwick escaped; satchel secured",
        "Fenwick secured; satchel lost",
        "Both lost",
    ]:
        check(outcome in outcome_section, f"Missing outcome: {outcome}")
    check("south dispatch-box entrance" in outcome_section,
          "Worst outcome must preserve an actionable Loomworks location")

    check(len(set(cipher.WRITTEN)) == 26, "Cipher must be a one-to-one alphabet")
    check(len({(ord(b)-ord(a)) % 26 for a,b in zip(cipher.PLAIN,cipher.WRITTEN)}) > 1,
          "Cipher must not be an alphabet shift")
    encrypted = cipher.encode(cipher.MEETING)
    message = cipher.handout(text,"### Player handout — Fenwick's encrypted reply")
    check(encrypted in message and cipher.decode(encrypted) == cipher.MEETING,
          "Fenwick handout does not decode to the stated meeting")
    for label in cipher.LABELS:
        check(cipher.encode(label) in negotiation,"Missing coded gift label: "+label)
    check(cipher.WRITTEN not in message and cipher.MEETING not in message,
          "Player letter must not expose the key or solution")
    check("A=D" not in text and "move each letter three" not in text,
          "The old printed Caesar key remains")
    check(cipher.encode(cipher.NEUTRAL_REPLY) in text,
          "Example reply is not correctly encrypted")
    available=set(cipher.MEETING+"".join(cipher.LABELS))
    check(set(cipher.NEUTRAL_REPLY) <= available,
          "The neutral reply requires a letter with no deduction source")
    check("Have a player write the plaintext, then encode it" in text,
          "Heroes must encrypt a message back to Fenwick")

    raw = MAP.read_bytes()[:24]
    check(raw[:8] == b"\x89PNG\r\n\x1a\n", "Lift-yard map is not a PNG")
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        width, height = struct.unpack(">II", raw[16:24])
        check((width, height) == (1422, 1106),
              f"Unexpected lift-yard map dimensions: {width}x{height}")
        check(width * 14 == height * 18, "Lift-yard map is not exactly 18:14")
    check("18 × 14-square yard" in text,
          "Run sheet and imported map dimensions must agree")

    broken_links: list[str] = []
    for path in (ROOT / "Campaign").rglob("*.md"):
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
            target = target.strip().strip("<>")
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            filepart = unquote(target.split("#", 1)[0])
            if filepart and not (path.parent / filepart).exists():
                broken_links.append(f"{path.relative_to(ROOT)} -> {target}")
    check(not broken_links, "Broken local links: " + "; ".join(broken_links))

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        raise SystemExit(1)
    print("SESSION_3_VALIDATION_OK")


if __name__ == "__main__":
    main()
