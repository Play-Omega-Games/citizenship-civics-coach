#!/usr/bin/env python3
"""Build data/questions.json from the official USCIS PDFs (text extracted with pdftotext -layout).

Verbatim policy: question and answer text is copied exactly as printed by USCIS,
only whitespace is normalized and the 65/20 asterisk is moved into a flag.
"""
import hashlib, json, re, sys
from pathlib import Path

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace/civics-coach/src")
OUT = Path(__file__).resolve().parent.parent / "data" / "questions.json"

SOURCES = {
    "2025": {
        "pdf": "2025-128.pdf", "txt": "2025-128.txt",
        "url": "https://www.uscis.gov/sites/default/files/document/questions-and-answers/2025-Civics-Test-128-Questions-and-Answers.pdf",
        "doc": "M-1778 (09/25), 128 Civics Questions and Answers (2025 version)",
        "bullet": "•", "expected": 128,
    },
    "2008": {
        "pdf": "2008-100-ooc.pdf", "txt": "2008-100-ooc.txt",
        "url": "https://www.uscis.gov/sites/default/files/document/questions-and-answers/OoC_100_Questions_2008_Civics_Test_V1.pdf",
        "doc": "Civics Questions and Answers (2008 version), rev. 08/21",
        "bullet": "▪", "expected": 100,
    },
}

PARTS = {"AMERICAN GOVERNMENT", "AMERICAN HISTORY", "SYMBOLS AND HOLIDAYS", "INTEGRATED CIVICS"}
NOISE = re.compile(r"(of 19\s+uscis\.gov/citizenship$|^-\d+-\s+www\.uscis\.gov$|^\* If you are 65|^may study just the questions)")

# Answers that USCIS says may change (elections, appointments, statute). Source: uscis.gov/citizenship/testupdates
CHANGES = {
    "2025": {23: "senator", 29: "representative", 30: "speaker", 38: "president", 39: "vice_president", 57: "chief_justice", 61: "governor"},
    "2008": {20: "senator", 23: "representative", 28: "president", 29: "vice_president", 39: "justices_count", 40: "chief_justice", 43: "governor", 46: "president_party", 47: "speaker"},
}
# Answer depends on where the applicant lives (not on the test updates page, but "Answers will vary").
STATE = {"2025": {23, 29, 61, 62}, "2008": {20, 23, 43, 44}}


def norm(s):
    s = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse(version):
    cfg = SOURCES[version]
    lines = (SRC / cfg["txt"]).read_text().splitlines()
    # skip the intro: start at first part heading
    start = next(i for i, l in enumerate(lines) if norm(l) == "AMERICAN GOVERNMENT")
    qs, part, section, cur, mode = [], None, None, None, None
    for raw in lines[start:]:
        l = norm(raw)
        if not l or NOISE.search(l) or l == "*":
            continue
        if l in PARTS:
            part = l.title(); mode = None; continue
        m = re.match(r"^([A-C]): (.+)$", l)
        if m:
            section = m.group(2); mode = None; continue
        m = re.match(r"^(\d+)\.\s*(.+)$", l)
        if m and (not qs or int(m.group(1)) == qs[-1]["number"] + 1):
            cur = {"number": int(m.group(1)), "question": m.group(2), "answers": [], "part": part, "section": section}
            qs.append(cur); mode = "q"; continue
        if l.startswith(cfg["bullet"]):
            cur["answers"].append(l[len(cfg["bullet"]):].strip()); mode = "a"; continue
        # standalone USCIS note printed under a list (2025 Q117)
        if l.startswith("For a complete list"):
            cur.setdefault("extra_notes", []).append(l); mode = None; continue
        # continuation line
        if mode == "q":
            cur["question"] += " " + l
        elif mode == "a":
            cur["answers"][-1] += " " + l
        else:
            raise SystemExit(f"{version}: unplaced line: {l!r}")
    out = []
    for q in qs:
        text = norm(q["question"])
        star = text.endswith("*")
        text = norm(text.rstrip("*"))
        n = q["number"]
        notes, answers = [], []
        # bracketed USCIS note inside the question line (2008 Q87)
        mq = re.match(r"^(.*?)\s*(\[.*\])$", text)
        if mq:
            text = mq.group(1); notes.append(mq.group(2))
        for a in q["answers"]:
            a = norm(a)
            # split trailing bracketed USCIS notes off into notes, keep answer verbatim otherwise
            mm = re.match(r"^(.*?)\s*(\[.*\])$", a)
            if mm and mm.group(1):
                answers.append(mm.group(1)); notes.append(mm.group(2))
            elif a.startswith("["):
                notes.append(a)
            else:
                answers.append(a)
        notes += q.get("extra_notes", [])
        if not answers:
            raise SystemExit(f"{version} Q{n}: no answers")
        out.append({
            "id": f"{version}-{n:03d}",
            "version": version,
            "number": n,
            "part": q["part"],
            "section": q["section"],
            "question": text,
            "answers": answers,
            "notes": notes,
            "flags": {
                "senior_65_20": star,
                "changes_over_time": n in CHANGES[version],
                "state_specific": n in STATE[version],
            },
            "current_answer_key": CHANGES[version].get(n),
        })
        out[-1]["standards"] = standards_for(out[-1])
    if len(out) != cfg["expected"]:
        raise SystemExit(f"{version}: parsed {len(out)} questions, expected {cfg['expected']}")
    return out


CIV3 = re.compile(r"Constitution|amendment|Bill of Rights|Declaration of Independence|documents?\b", re.I)
CAUSE = re.compile(r"\b(why|reasons?|problem that led)\b", re.I)


def standards_for(q):
    """C3 tags by activity (see data/standards.json). Only clear fits; anything unclear gets no tag."""
    tags = []
    sec, part = q["section"], q["part"]
    if sec.startswith("Principles of American"):
        tags.append("D2.Civ.5.6-8")
    if sec == "System of Government":
        tags.append("D2.Civ.4.6-8")
    if sec == "Rights and Responsibilities":
        tags += ["D2.Civ.2.6-8", "D2.Civ.2.9-12"]
    if CIV3.search(q["question"]) and part == "American Government":
        tags.append("D2.Civ.3.6-8")
    if part == "American History" and CAUSE.search(q["question"]) and "important" not in q["question"]:
        tags.append("D2.His.14.6-8")
    return tags


def sha(p):
    return hashlib.sha256((SRC / p).read_bytes()).hexdigest()


def main():
    data = {
        "title": "USCIS naturalization civics test questions (official, verbatim)",
        "license": "U.S. government work (17 U.S.C. 105), public domain. Not affiliated with or endorsed by USCIS.",
        "retrieved": "2026-11-24",
        "test_updates_url": "https://www.uscis.gov/citizenship/testupdates",
        "versions": {},
        "questions": [],
    }
    for v, cfg in SOURCES.items():
        qs = parse(v)
        data["versions"][v] = {
            "source_url": cfg["url"], "document": cfg["doc"], "source_sha256": sha(cfg["pdf"]),
            "count": len(qs), "senior_65_20_count": sum(q["flags"]["senior_65_20"] for q in qs),
        }
        data["questions"] += qs
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    for v, i in data["versions"].items():
        print(v, i["count"], "questions,", i["senior_65_20_count"], "marked 65/20")


if __name__ == "__main__":
    main()
