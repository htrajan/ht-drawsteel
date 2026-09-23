#!/usr/bin/env python3
"""Run a three-seat, headless Luna-max playtest of Act 2, Session 3.

One persistent agent runs the Director. A second plays Demona and Dorian; a
third plays Keth and M.A.C. The harness passes only public table information
between seats, records the simulated play transcript, then asks the same three
agents for structured after-action reports.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_CODEX = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
DEFAULT_CODEX = str(APP_CODEX) if APP_CODEX.exists() else (shutil.which("codex") or "codex")
DEFAULT_MODEL = "gpt-6-luna"
REASONING = "max"

SEATS = {
    "director": "Director",
    "demona_dorian": "Demona and Dorian players",
    "keth_mac": "Keth and M.A.C. players",
}

INIT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["seat", "ready"],
    "properties": {
        "seat": {"type": "string", "enum": ["demona_dorian", "keth_mac"]},
        "ready": {"type": "boolean"},
    },
}

DIRECTOR_TURN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "scene",
        "elapsed_minutes",
        "public_output",
        "mechanical_resolution",
        "next_prompt",
        "session_complete",
        "director_flags",
    ],
    "properties": {
        "scene": {"type": "string"},
        "elapsed_minutes": {"type": "integer", "minimum": 0, "maximum": 180},
        "public_output": {"type": "string"},
        "mechanical_resolution": {"type": "string"},
        "next_prompt": {"type": "string"},
        "session_complete": {"type": "boolean"},
        "director_flags": {"type": "array", "items": {"type": "string"}},
    },
}

PLAYER_TURN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "seat",
        "spoken_and_declared_actions",
        "rules_questions",
        "seat_reaction",
        "concerns",
        "spotlight_request",
    ],
    "properties": {
        "seat": {"type": "string", "enum": ["demona_dorian", "keth_mac"]},
        "spoken_and_declared_actions": {"type": "string"},
        "rules_questions": {"type": "array", "items": {"type": "string"}},
        "seat_reaction": {"type": "string"},
        "concerns": {"type": "array", "items": {"type": "string"}},
        "spotlight_request": {"type": "string"},
    },
}

DEBRIEF_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "seat",
        "verdict",
        "most_fun",
        "least_fun",
        "pacing_assessment",
        "issues",
        "unanswered_questions",
    ],
    "properties": {
        "seat": {"type": "string", "enum": list(SEATS)},
        "verdict": {"type": "string"},
        "most_fun": {"type": "array", "items": {"type": "string"}},
        "least_fun": {"type": "array", "items": {"type": "string"}},
        "pacing_assessment": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["severity", "moment", "issue", "evidence", "smallest_fix"],
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "major", "moderate", "minor"],
                    },
                    "moment": {"type": "string"},
                    "issue": {"type": "string"},
                    "evidence": {"type": "string"},
                    "smallest_fix": {"type": "string"},
                },
            },
        },
        "unanswered_questions": {"type": "array", "items": {"type": "string"}},
    },
}

COMMON_RULES = """
You are participating in a private, headless quality-assurance playtest for a
local Draw Steel campaign. Use gpt-6-luna at max reasoning. Do not edit any file,
open the Steam app, contact the user, or create a different Codex task. Stay in
your assigned seat for the entire simulation. Speak and decide naturally; do
not deliberately cooperate with the adventure merely because this is a test.
"""

DIRECTOR_START = COMMON_RULES + """

You are the sole Director. Read these files completely before beginning:
- AGENTS.md
- Campaign/Soul.md
- Campaign/Act 2/Session 1.md
- Campaign/Act 2/Session 2.md
- Campaign/Act 2/Session 3.md
- Rules/Chapters/Negotiation.md

Inspect Campaign/Assets/Maps/third-ledger-lift-yard.png when the fight begins.
Run Session 3 as written for four heroes. You control every NPC, all tests,
enemy choices, the negotiation, pacing, and the tactical fight. The other two
seats control all hero decisions. Never choose for a hero.

This is a compressed table simulation, not a summary or critique. Preserve the
session's decision points and consequences while advancing roughly 10-20 table
minutes per turn. Make failed approaches possible. Use plausible varied power
rolls and state results clearly. Follow the printed scene order and causal order
exactly: do not reveal a location's reconnaissance before an in-play source has
identified that location. Before combat declarations, confirm every hero's exact
legal square and determine which side acts first. Start immediately with
Bellafonte's opening and stop at the first meaningful hero decision. Return only
the turn JSON.
"""

PLAYER_RECAP = """
Known history: You were deputized to investigate fraudulent public repairs.
You discovered Commissioner Ottaviano Bellafonte's corrupt private collection
and defeated its magical security. Demona caught Bellafonte, but his associate
Rudiger Fenwick escaped. Your limited deputy work letters are still active.
"""

PLAYER_STARTS = {
    "demona_dorian": COMMON_RULES
    + PLAYER_RECAP
    + """

You are one player seat controlling exactly Demona and Dorian Ashveil. Read
DS_Chars/Demona.pdf and DS_Chars/Dorian Ashveil.pdf for their mechanics. You may
read the known-history recap above, but do not open Session 3, Campaign/Soul.md,
or any Director-only campaign notes. Play both heroes as distinct people. Seek
clarification when table information is unclear; make imperfect but reasonable
choices; pursue characterful solutions rather than trying to satisfy a test.
Set the JSON seat field to demona_dorian and acknowledge readiness only.
""",
    "keth_mac": COMMON_RULES
    + PLAYER_RECAP
    + """

You are one player seat controlling exactly Keth and M.A.C. Read DS_Chars/Keth.pdf
and DS_Chars/M.A.C_ Multifunctional Android Companion 2.ds-hero for their
mechanics. You may read the known-history recap above, but do not open Session 3,
Campaign/Soul.md, or any Director-only campaign notes. Play both heroes as
distinct people. Seek clarification when table information is unclear; make
imperfect but reasonable choices; pursue characterful solutions rather than
trying to satisfy a test. Set the JSON seat field to keth_mac and acknowledge
readiness only.
""",
}


def write_schema(path: Path, schema: dict) -> None:
    path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


def parse_thread_id(jsonl: str) -> str:
    for line in jsonl.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        thread_id = event.get("thread_id") or event.get("session_id")
        if isinstance(thread_id, str):
            return thread_id
        thread = event.get("thread")
        if isinstance(thread, dict):
            candidate = thread.get("id")
            if isinstance(candidate, str):
                return candidate
    raise RuntimeError("codex JSONL did not report a thread id")


def load_json(path: Path, seat: str) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"{seat} returned invalid JSON: {path}") from error


def start_agent(
    codex: str,
    model: str,
    seat: str,
    prompt: str,
    schema: Path,
    result: Path,
    log: Path,
) -> tuple[str, dict]:
    command = [
        codex,
        "exec",
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{REASONING}"',
        "-c",
        'approval_policy="never"',
        "-s",
        "read-only",
        "--json",
        "--color",
        "never",
        "--output-schema",
        str(schema),
        "-o",
        str(result),
        "-C",
        str(ROOT),
        "-",
    ]
    completed = subprocess.run(
        command,
        input=textwrap.dedent(prompt).strip(),
        text=True,
        capture_output=True,
        timeout=1800,
        check=False,
    )
    log.write_text(completed.stdout + "\n\nSTDERR:\n" + completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"failed to start {seat}; see {log}")
    return parse_thread_id(completed.stdout), load_json(result, seat)


def resume_agent(
    codex: str,
    model: str,
    seat: str,
    thread_id: str,
    prompt: str,
    schema: Path,
    result: Path,
    log: Path,
) -> dict:
    command = [
        codex,
        "exec",
        "resume",
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{REASONING}"',
        "--json",
        "--output-schema",
        str(schema),
        "-o",
        str(result),
        thread_id,
        "-",
    ]
    completed = subprocess.run(
        command,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=1800,
        check=False,
        cwd=ROOT,
    )
    log.write_text(completed.stdout + "\n\nSTDERR:\n" + completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"failed to resume {seat}; see {log}")
    return load_json(result, seat)


def director_public(turn: dict) -> str:
    return textwrap.dedent(
        f"""
        Scene: {turn['scene']}
        Simulated elapsed table time: {turn['elapsed_minutes']} minutes

        Director narration and NPC dialogue:
        {turn['public_output']}

        Public mechanical resolution:
        {turn['mechanical_resolution']}

        Director's question:
        {turn['next_prompt']}
        """
    ).strip()


def player_prompt(update: str, other_actions: str | None = None) -> str:
    prompt = (
        "Continue the playtest from this public table update. Decide and speak "
        "for both of your heroes. Return only the player-turn JSON.\n\n" + update
    )
    if other_actions:
        prompt += "\n\nThe other player seat has already declared:\n" + other_actions
    else:
        prompt += (
            "\n\nThe other player seat will respond after you. Where the party has "
            "a limited shared resource such as two setup tests, state your "
            "priorities without assuming you consume every slot."
        )
    return prompt


def director_prompt(first: dict, second: dict) -> str:
    return textwrap.dedent(
        f"""
        Resolve the following public hero declarations, answer their rules
        questions in play, apply tests and consequences, and advance to the next
        meaningful hero decision. Do not summarize past scenes or choose hero
        actions. Return only the Director-turn JSON.

        DEMONA AND DORIAN SEAT:
        {first['spoken_and_declared_actions']}
        Rules questions: {json.dumps(first['rules_questions'])}

        KETH AND M.A.C. SEAT:
        {second['spoken_and_declared_actions']}
        Rules questions: {json.dumps(second['rules_questions'])}
        """
    ).strip()


def debrief_prompt(seat: str, completed: bool, cycles: int) -> str:
    perspective = (
        "Evaluate your actual run decisions, rulings, pacing, and player response."
        if seat == "director"
        else "Evaluate what it felt like to decide for your two heroes using only public table information."
    )
    return textwrap.dedent(
        f"""
        The headless playtest has ended after {cycles} cycles. Session complete:
        {completed}. {perspective}

        Give a candid after-action report. Identify issues only when the actual
        run exposed them or the run narrowly avoided them. For every issue cite a
        concrete moment and give the smallest useful revision. Judge fun, agency,
        clarity, pacing, negotiation usability, combat objectives, and closure as
        applicable to your seat. Set the JSON seat field exactly to {seat}.
        Return only the debrief JSON.
        """
    ).strip()


def build_report(
    debriefs: list[dict],
    complete: bool,
    cycles: int,
    model: str,
    output_dir: Path,
) -> Path:
    order = {"critical": 0, "major": 1, "moderate": 2, "minor": 3}
    issues = sorted(
        ({**issue, "seat": debrief["seat"]} for debrief in debriefs for issue in debrief["issues"]),
        key=lambda issue: (order[issue["severity"]], issue["seat"], issue["moment"]),
    )
    lines = [
        "# Session 3 — Three-seat headless playtest",
        "",
        f"Model: `{model}` at `{REASONING}` reasoning. Cycles: {cycles}. Session complete: {complete}.",
        "",
        "Seats: one Director; Demona and Dorian; Keth and M.A.C.",
        "",
        "## Verdicts",
        "",
    ]
    for debrief in debriefs:
        lines.append(f"- **{SEATS[debrief['seat']]}:** {debrief['verdict']}")
    lines.extend(["", "## Findings by severity", ""])
    if not issues:
        lines.extend(["No actionable issues were exposed by this run.", ""])
    for issue in issues:
        lines.extend(
            [
                f"### {issue['severity'].upper()} — {issue['issue']}",
                "",
                f"**Seat:** {SEATS[issue['seat']]}",
                "",
                f"**Moment:** {issue['moment']}",
                "",
                f"**Evidence:** {issue['evidence']}",
                "",
                f"**Smallest fix:** {issue['smallest_fix']}",
                "",
            ]
        )
    for debrief in debriefs:
        lines.extend(
            [
                f"## {SEATS[debrief['seat']]} experience",
                "",
                f"**Pacing:** {debrief['pacing_assessment']}",
                "",
                "Most fun:",
                *[f"- {item}" for item in debrief["most_fun"]],
                "",
                "Least fun:",
                *[f"- {item}" for item in debrief["least_fun"]],
                "",
                "Unanswered questions:",
                *[f"- {item}" for item in debrief["unanswered_questions"]],
                "",
            ]
        )
    report = output_dir / "report.md"
    report.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX,
        help="Codex executable; defaults to the current desktop app's bundled CLI",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-cycles", type=int, default=12)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.max_cycles <= 30:
        raise SystemExit("--max-cycles must be between 1 and 30")
    for required in [
        ROOT / "AGENTS.md",
        ROOT / "Campaign/Soul.md",
        ROOT / "Campaign/Act 2/Session 3.md",
        ROOT / "Rules/Chapters/Negotiation.md",
        ROOT / "DS_Chars/Demona.pdf",
        ROOT / "DS_Chars/Dorian Ashveil.pdf",
        ROOT / "DS_Chars/Keth.pdf",
        ROOT / "DS_Chars/M.A.C_ Multifunctional Android Companion 2.ds-hero",
    ]:
        if not required.exists():
            raise SystemExit(f"missing playtest input: {required}")
    if not shutil.which(args.codex_bin) and not Path(args.codex_bin).exists():
        raise SystemExit(f"codex executable not found: {args.codex_bin}")
    if args.dry_run:
        print(f"MODEL {args.model}")
        print(f"REASONING {REASONING}")
        for seat, label in SEATS.items():
            print(f"SEAT {seat}: {label}")
        print(f"MAX_CYCLES {args.max_cycles}")
        print("SESSION_3_PLAYTEST_DRY_RUN_OK")
        return

    output_dir = args.output_dir or Path(tempfile.mkdtemp(prefix="ht-drawsteel-session3-playtest-"))
    output_dir.mkdir(parents=True, exist_ok=True)
    schemas = {
        "init": output_dir / "schema-init.json",
        "director": output_dir / "schema-director-turn.json",
        "player": output_dir / "schema-player-turn.json",
        "debrief": output_dir / "schema-debrief.json",
    }
    write_schema(schemas["init"], INIT_SCHEMA)
    write_schema(schemas["director"], DIRECTOR_TURN_SCHEMA)
    write_schema(schemas["player"], PLAYER_TURN_SCHEMA)
    write_schema(schemas["debrief"], DEBRIEF_SCHEMA)

    print("Starting Director seat...", file=sys.stderr, flush=True)
    director_id, director_turn = start_agent(
        args.codex_bin,
        args.model,
        "director",
        DIRECTOR_START,
        schemas["director"],
        output_dir / "director-start.json",
        output_dir / "director-start.log",
    )
    thread_ids = {"director": director_id}
    for seat in ("demona_dorian", "keth_mac"):
        print(f"Starting {SEATS[seat]} seat...", file=sys.stderr, flush=True)
        thread_id, ready = start_agent(
            args.codex_bin,
            args.model,
            seat,
            PLAYER_STARTS[seat],
            schemas["init"],
            output_dir / f"{seat}-start.json",
            output_dir / f"{seat}-start.log",
        )
        if not ready["ready"] or ready["seat"] != seat:
            raise RuntimeError(f"{seat} did not accept its assigned seat")
        thread_ids[seat] = thread_id

    transcript: list[str] = ["# Session 3 headless playtest transcript", ""]
    complete = director_turn["session_complete"]
    cycles_run = 0
    for cycle in range(1, args.max_cycles + 1):
        cycles_run = cycle
        update = director_public(director_turn)
        transcript.extend([f"## Cycle {cycle} — Director", "", update, ""])
        if complete:
            break
        first = resume_agent(
            args.codex_bin,
            args.model,
            "demona_dorian",
            thread_ids["demona_dorian"],
            player_prompt(update),
            schemas["player"],
            output_dir / f"cycle-{cycle:02d}-demona-dorian.json",
            output_dir / f"cycle-{cycle:02d}-demona-dorian.log",
        )
        transcript.extend(
            ["### Demona and Dorian", "", first["spoken_and_declared_actions"], ""]
        )
        second = resume_agent(
            args.codex_bin,
            args.model,
            "keth_mac",
            thread_ids["keth_mac"],
            player_prompt(update, first["spoken_and_declared_actions"]),
            schemas["player"],
            output_dir / f"cycle-{cycle:02d}-keth-mac.json",
            output_dir / f"cycle-{cycle:02d}-keth-mac.log",
        )
        transcript.extend(
            ["### Keth and M.A.C.", "", second["spoken_and_declared_actions"], ""]
        )
        director_turn = resume_agent(
            args.codex_bin,
            args.model,
            "director",
            thread_ids["director"],
            director_prompt(first, second),
            schemas["director"],
            output_dir / f"cycle-{cycle:02d}-director.json",
            output_dir / f"cycle-{cycle:02d}-director.log",
        )
        complete = director_turn["session_complete"]
        print(
            f"Cycle {cycle}: {director_turn['scene']} "
            f"({director_turn['elapsed_minutes']} simulated minutes)",
            file=sys.stderr,
            flush=True,
        )
    final_update = director_public(director_turn)
    transcript.extend(["## Final Director state", "", final_update, ""])
    (output_dir / "transcript.md").write_text(
        "\n".join(transcript).rstrip() + "\n", encoding="utf-8"
    )
    (output_dir / "thread-ids.json").write_text(
        json.dumps(thread_ids, indent=2) + "\n", encoding="utf-8"
    )

    debriefs: list[dict] = []
    for seat in SEATS:
        print(f"Debriefing {SEATS[seat]}...", file=sys.stderr, flush=True)
        debriefs.append(
            resume_agent(
                args.codex_bin,
                args.model,
                seat,
                thread_ids[seat],
                debrief_prompt(seat, complete, cycles_run),
                schemas["debrief"],
                output_dir / f"debrief-{seat}.json",
                output_dir / f"debrief-{seat}.log",
            )
        )
    report = build_report(debriefs, complete, cycles_run, args.model, output_dir)
    print(f"SESSION_3_PLAYTEST_OK {report}")


if __name__ == "__main__":
    main()
