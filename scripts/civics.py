"""Citizenship Civics Coach engine: test version, Leitner drills, mock tests, readiness numbers
and live lookups for answers that change. Standard library only. Data paths are relative to the repo root.

    python3 scripts/civics.py version --filed 2025-09-30            # which test applies (or --not-filed)
    python3 scripts/civics.py deck --version 2025 [--senior]
    python3 scripts/civics.py init --version 2025 [--senior] --daily 10 --start 2026-11-25 [--interview 2027-02-10] --out state/progress.json
    python3 scripts/civics.py today --progress state/progress.json --date 2026-11-25
    python3 scripts/civics.py record --progress state/progress.json --date 2026-11-25 --id 2025-038 --result right|wrong
    python3 scripts/civics.py mock --version 2025 [--senior] --seed <salt>-<date>
    python3 scripts/civics.py mock-score --version 2025 [--senior] --results "RRWRR..."
    python3 scripts/civics.py stats --progress state/progress.json --date 2026-11-25
    python3 scripts/civics.py current federal --version 2025          # live from uscis.gov/citizenship/testupdates
    python3 scripts/civics.py current senators --state OH             # live from senate.gov
    python3 scripts/civics.py current governor --state ohio           # live from usa.gov
    python3 scripts/civics.py current representative --state OH [--district 3]   # live from clerk.house.gov
    python3 scripts/civics.py current capital --state OH                # data/capitals.json (stable)
    python3 scripts/civics.py log-session --progress state/progress.json --date 2026-11-25 --minutes 9 --kind drill
    python3 scripts/civics.py report --progress state/progress.json --date 2026-11-29     # printable report (Markdown)
    python3 scripts/civics.py snapshot --progress state/progress.json      # one line for memory
    python3 scripts/civics.py restore --line "<snapshot>" --salt <salt> --out state/progress.json
    python3 scripts/civics.py validate
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import random
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data' / 'questions.json'
CUTOFF = dt.date(2025, 10, 20)  # N-400 filed on or after this date: 2025 test (uscis.gov/citizenship/testupdates)
RULES = {
    # asked, pass_at, fail_at (officer stops at whichever comes first)
    ('2025', False): {'pool': 128, 'asked': 20, 'pass_at': 12, 'fail_at': 9},
    ('2008', False): {'pool': 100, 'asked': 10, 'pass_at': 6, 'fail_at': 5},
    ('2025', True): {'pool': 20, 'asked': 10, 'pass_at': 6, 'fail_at': 5},
    ('2008', True): {'pool': 20, 'asked': 10, 'pass_at': 6, 'fail_at': 5},
}
BOXES = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}  # Leitner box -> days until next review
TEST_UPDATES = 'https://www.uscis.gov/citizenship/testupdates'
UA = 'Mozilla/5.0 (compatible; CitizenshipCivicsCoach/1.0)'
STATES = {
    'AL': 'alabama', 'AK': 'alaska', 'AZ': 'arizona', 'AR': 'arkansas', 'CA': 'california', 'CO': 'colorado',
    'CT': 'connecticut', 'DE': 'delaware', 'FL': 'florida', 'GA': 'georgia', 'HI': 'hawaii', 'ID': 'idaho',
    'IL': 'illinois', 'IN': 'indiana', 'IA': 'iowa', 'KS': 'kansas', 'KY': 'kentucky', 'LA': 'louisiana',
    'ME': 'maine', 'MD': 'maryland', 'MA': 'massachusetts', 'MI': 'michigan', 'MN': 'minnesota',
    'MS': 'mississippi', 'MO': 'missouri', 'MT': 'montana', 'NE': 'nebraska', 'NV': 'nevada',
    'NH': 'new-hampshire', 'NJ': 'new-jersey', 'NM': 'new-mexico', 'NY': 'new-york', 'NC': 'north-carolina',
    'ND': 'north-dakota', 'OH': 'ohio', 'OK': 'oklahoma', 'OR': 'oregon', 'PA': 'pennsylvania',
    'RI': 'rhode-island', 'SC': 'south-carolina', 'SD': 'south-dakota', 'TN': 'tennessee', 'TX': 'texas',
    'UT': 'utah', 'VT': 'vermont', 'VA': 'virginia', 'WA': 'washington', 'WV': 'west-virginia',
    'WI': 'wisconsin', 'WY': 'wyoming',
    'DC': 'district-of-columbia', 'PR': 'puerto-rico', 'GU': 'guam', 'VI': 'u-s-virgin-islands',
    'AS': 'american-samoa', 'MP': 'northern-mariana-islands',
}
TERRITORIES = {'PR', 'GU', 'VI', 'AS', 'MP'}


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=1))


def load():
    return json.loads(DATA.read_text())


def deck(version, senior=False):
    qs = [q for q in load()['questions'] if q['version'] == version]
    if senior:
        qs = [q for q in qs if q['flags']['senior_65_20']]
    return qs


def rng_for(*parts):
    h = hashlib.sha256('|'.join(str(p) for p in parts).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def d(s):
    return dt.date.fromisoformat(s)


# ------------------------------------------------------------------ version
def which_version(filed=None):
    if filed is None:
        return {'version': '2025', 'reason': 'Not filed yet. Anyone filing Form N-400 on or after Oct 20, 2025 takes the 2025 test.',
                'source': TEST_UPDATES}
    v = '2025' if d(filed) >= CUTOFF else '2008'
    return {'version': v, 'reason': f'Form N-400 filed {filed}: '
            + ('on or after Oct 20, 2025, so the 2025 test.' if v == '2025' else 'before Oct 20, 2025, so the 2008 test.'),
            'source': TEST_UPDATES}


# ------------------------------------------------------------------ Leitner progress
def init(version, senior, daily, start, interview=None, salt=None):
    order = [q['id'] for q in deck(version, senior)]
    rng_for(salt or 'order', version, senior).shuffle(order)
    return {'version': version, 'senior': senior, 'daily': daily, 'start': start, 'interview': interview,
            'new_order': order, 'cards': {}, 'log': [], 'mocks': [], 'sessions': []}


def due(p, day):
    return sorted((cid for cid, c in p['cards'].items() if d(c['due']) <= day),
                  key=lambda cid: (p['cards'][cid]['box'], p['cards'][cid]['due'], cid))


def new_per_day(p, day):
    """New cards per day: a share of the daily count, raised so every card is seen at least 14 days before the interview."""
    left = [cid for cid in p['new_order'] if cid not in p['cards']]
    base = max(1, p['daily'] // 2)
    if p.get('interview') and left:
        days = (d(p['interview']) - dt.timedelta(days=14) - day).days + 1
        if days > 0:
            need = -(-len(left) // days)
            base = max(base, need)
        else:
            base = max(base, len(left))  # inside two weeks: introduce everything still unseen, reviews come first
    return min(base, len(left)), left


def today(p, day):
    reviews = due(p, day)
    n_new, left = new_per_day(p, day)
    cap = p['daily']
    picked = reviews[:cap]
    room = max(0, cap - len(picked))
    fresh = left[:min(n_new, room)] if room else []
    warn = None
    if p.get('interview') and n_new > max(1, p['daily'] // 2):
        warn = (f'To see every question at least two weeks before your interview, {n_new} new questions a day are needed. '
                f'A bigger daily count would help.')
    qs = {q['id']: q for q in deck(p['version'], p['senior'])}
    return {'date': day.isoformat(), 'reviews': picked, 'new': fresh,
            'questions': [qs[i] for i in picked + fresh], 'reviews_waiting': max(0, len(reviews) - len(picked)),
            'unseen_left': len(left), 'pace_note': warn}


def record(p, day, cid, result):
    c = p['cards'].get(cid, {'box': 0, 'seen': 0, 'right': 0})
    c['seen'] += 1
    if result == 'right':
        c['right'] += 1
        c['box'] = min(5, max(c['box'], 1) + 1)  # a new card answered right starts in box 2
    else:
        c['box'] = 1
    c['due'] = (day + dt.timedelta(days=BOXES[c['box']])).isoformat()
    c['last'] = day.isoformat()
    p['cards'][cid] = c
    p['log'].append([day.isoformat(), cid, result[0]])
    return c


def log_session(p, day, minutes, kind):
    """Minutes come from the chat: first question sent to last answer, rounded up, capped at 90. Never estimated."""
    p.setdefault('sessions', []).append({'date': day.isoformat(), 'minutes': max(1, min(90, int(minutes))), 'kind': kind})
    return p['sessions'][-1]


def standards_practiced(p):
    std = {s['code']: s for s in json.loads((ROOT / 'data' / 'standards.json').read_text())['standards']}
    rows = {}
    for q in deck(p['version'], p['senior']):
        for code in q.get('standards', []):
            r = rows.setdefault(code, {'code': code, 'text': std[code]['text'], 'band': std[code]['band'],
                                       'activity': std[code]['activity'], 'questions': 0, 'practiced': 0, 'solid': 0})
            r['questions'] += 1
            c = p['cards'].get(q['id'])
            if c and c.get('right', 0) > 0:
                r['practiced'] += 1
            if c and c['box'] >= 4:
                r['solid'] += 1
    return list(rows.values())


def stats(p, day):
    qs = deck(p['version'], p['senior'])
    boxes = {b: 0 for b in range(0, 6)}
    cats = {}
    for q in qs:
        c = p['cards'].get(q['id'])
        b = c['box'] if c else 0
        boxes[b] += 1
        key = q['section']
        cats.setdefault(key, {'total': 0, 'box4plus': 0})
        cats[key]['total'] += 1
        cats[key]['box4plus'] += b >= 4
    days = sorted({e[0] for e in p['log']})
    streak, cur = 0, day
    if days and d(days[-1]) < day:
        cur = day - dt.timedelta(days=1)
    while cur.isoformat() in days:
        streak += 1
        cur -= dt.timedelta(days=1)
    r = RULES[(p['version'], p['senior'])]
    last_mocks = p['mocks'][-4:]
    return {
        'total': len(qs), 'unseen': boxes[0], 'boxes': {str(b): boxes[b] for b in range(1, 6)},
        'solid': boxes[4] + boxes[5],  # box 4 or 5 = answered right at least 4 times in a row
        'categories': cats, 'study_days': len(days), 'streak': streak,
        'due_tomorrow': len(due(p, day + dt.timedelta(days=1))),
        'days_to_interview': (d(p['interview']) - day).days if p.get('interview') else None,
        'mock_rule': r, 'recent_mocks': last_mocks,
        'mastered': boxes[5],  # Library Card "collected": questions in box 5
        'days_log': sorted({x['date'] for x in p.get('sessions', [])} | set(days)),
        'study_days_total': len({x['date'] for x in p.get('sessions', [])} | {e[0] for e in p['log'] if e[1] != 'restored'}) + p.get('restored_days', 0),
        'minutes_total': sum(x['minutes'] for x in p.get('sessions', [])) + p.get('restored_minutes', 0),
        'minutes_last_7': sum(x['minutes'] for x in p.get('sessions', []) if (day - d(x['date'])).days < 7),
        'standards': standards_practiced(p),
        'mock_passes_in_a_row': next((i for i, m in enumerate(reversed(p['mocks'])) if not m['passed']), len(p['mocks'])),
    }


def snapshot(p):
    """Compact line for memory: one digit (Leitner box 0-5) per question in deck order, plus the last study date."""
    ids = [q['id'] for q in deck(p['version'], p['senior'])]
    boxes = ''.join(str(p['cards'].get(i, {}).get('box', 0)) for i in ids)
    last = max((c['last'] for c in p['cards'].values()), default=None)
    m = ','.join(f"{x['date']}:{x['right']}/{x['asked']}" for x in p['mocks'][-4:])
    days = len({x['date'] for x in p.get('sessions', [])} | {e[0] for e in p['log'] if e[1] != 'restored'}) + p.get('restored_days', 0)
    mins = sum(x['minutes'] for x in p.get('sessions', [])) + p.get('restored_minutes', 0)
    return (f"v={p['version']} senior={int(p['senior'])} daily={p['daily']} start={p['start']} interview={p.get('interview') or '-'} "
            f"last={last or '-'} days={days} minutes={mins} boxes={boxes} mocks={m or '-'}")


def restore(line, salt=None):
    kv = dict(part.split('=', 1) for part in line.split())
    senior = kv['senior'] == '1'
    p = init(kv['v'], senior, int(kv['daily']), kv['start'], None if kv['interview'] == '-' else kv['interview'], salt)
    ids = [q['id'] for q in deck(kv['v'], senior)]
    last = None if kv['last'] == '-' else d(kv['last'])
    for i, b in zip(ids, kv['boxes']):
        b = int(b)
        if b and last:
            p['cards'][i] = {'box': b, 'seen': b, 'right': b - 1, 'last': last.isoformat(),
                             'due': (last + dt.timedelta(days=BOXES[b])).isoformat()}
    if kv.get('mocks', '-') != '-':
        for m in kv['mocks'].split(','):
            date, score = m.split(':'); right, asked = score.split('/')
            r = RULES[(kv['v'], senior)]
            p['mocks'].append({'date': date, 'right': int(right), 'asked': int(asked), 'wrong': int(asked) - int(right),
                               'passed': int(right) >= r['pass_at']})
    if last:
        p['log'].append([last.isoformat(), 'restored', 'r'])
    p['restored_days'] = int(kv.get('days', 0))
    p['restored_minutes'] = int(kv.get('minutes', 0))
    return p


def report(p, day, name=None):
    """Printable progress report (Markdown) from the Library Card numbers."""
    st = stats(p, day)
    r = st['mock_rule']
    lines = [f"# Civics study report{(' for ' + name) if name else ''}", '',
             f"Test: {p['version']} civics test{' (65/20 list)' if p['senior'] else ''}. Report date: {day.isoformat()}.", '',
             '## Attendance', f"- Study days: {st['study_days_total']}", f"- Minutes logged: {st['minutes_total']}", '',
             '## Progress', f"- Questions in plan: {st['total']}", f"- Not seen yet: {st['unseen']}",
             f"- Solid (box 4 or 5): {st['solid']}", f"- Mastered (box 5): {st['mastered']}", '',
             '## Practice tests', f"Rule: up to {r['asked']} asked, pass at {r['pass_at']} right.", '']
    if p['mocks']:
        lines += ['| Date | Right | Wrong | Asked | Passed |', '|---|---|---|---|---|']
        lines += [f"| {m['date']} | {m['right']} | {m['wrong']} | {m['asked']} | {'yes' if m['passed'] else 'no'} |" for m in p['mocks']]
    else:
        lines.append('None yet.')
    lines += ['', '## Standards practiced (C3 Framework, supports practice toward)']
    lines += [f"- {x['code']}: {x['text']} ({x['practiced']} of {x['questions']} questions practiced, {x['solid']} solid)" for x in st['standards']]
    lines += ['', 'Study aid only. Not legal advice. Not affiliated with or endorsed by USCIS or any government agency.',
              'Questions: official USCIS civics test list (uscis.gov/citizenship). Standards: C3 Framework, NCSS (socialstudies.org/standards/c3).']
    return '\n'.join(lines) + '\n'


# ------------------------------------------------------------------ mock test
def mock(version, senior, seed):
    r = RULES[(version, senior)]
    pool = deck(version, senior)
    rng = rng_for('mock', seed, version, senior)
    picked = rng.sample(pool, r['asked'])
    return {'version': version, 'senior': senior, 'rule': r, 'questions': picked,
            'note': 'Questions are picked at random. The real test is drawn by a USCIS system and asked aloud by an officer.'}


def mock_score(version, senior, results):
    r = RULES[(version, senior)]
    right = wrong = asked = 0
    stopped = None
    for ch in results.upper():
        if ch not in 'RW':
            continue
        asked += 1
        right += ch == 'R'
        wrong += ch == 'W'
        if right >= r['pass_at']:
            stopped = 'pass'; break
        if wrong >= r['fail_at']:
            stopped = 'fail'; break
    return {'asked': asked, 'right': right, 'wrong': wrong, 'passed': right >= r['pass_at'],
            'finished': stopped is not None or asked >= r['asked'], 'stopped_because': stopped, 'rule': r}


# ------------------------------------------------------------------ live lookups (never cached in the repo)
def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode('utf-8', 'replace')


def text_of(page):
    page = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', page, flags=re.S)
    page = re.sub(r'<[^>]+>', '\n', page)
    lines = [re.sub(r'\s+', ' ', html.unescape(l)).strip() for l in page.split('\n')]
    return [l for l in lines if l]


def current_federal(version):
    """Read the answers on USCIS's Check for Test Updates page for one test version."""
    lines = text_of(fetch(TEST_UPDATES))
    ri = next((i for i, l in enumerate(lines) if l.startswith('Last Reviewed/Updated')), None)
    reviewed = None
    if ri is not None:
        m = re.search(r'\d{2}/\d{2}/\d{4}', ' '.join(lines[ri:ri + 2]))
        reviewed = m.group(0) if m else None
    head = 'Civics Test (2008 Version) Updates' if version == '2008' else 'Civics Test (2025 Naturalization Civics Test) Updates'
    try:
        i = lines.index(head)
    except ValueError:
        raise SystemExit('USCIS page layout changed: section heading not found. Send the owner to ' + TEST_UPDATES)
    items, cur = {}, None
    for l in lines[i + 1:]:
        if l.startswith('Civics Test (') or l.startswith('Last Reviewed'):
            break
        m = re.match(r'^(\d+)\.\s*(.+)$', l)
        if m:
            cur = int(m.group(1)); items[cur] = {'question': m.group(2).replace(' ?', '?').rstrip('* ').strip(), 'answers': []}
        elif cur:
            if re.fullmatch(r'[*?\s]+', l):
                if '?' in l and not items[cur]['question'].endswith('?'):
                    items[cur]['question'] += '?'
                continue
            items[cur]['answers'].append(l)
    for n, it in items.items():
        # join "Visit senate.gov to find ..." fragments that the link markup split up
        joined = ' '.join(it['answers'])
        it['answers'] = [a for a in it['answers'] if not a.startswith(('Visit', 'to find', 'senate.gov', 'house.gov', 'usa.gov'))]
        it['answers'] = [a for a in it['answers'] if a not in ('to find your state’s U.S. Senators.', 'to find your U.S. Representative.', 'to find the Governor of your state.')]
        it['answers'] = [re.sub(r'\s*Visit$', '', a) for a in it['answers']]
        it['raw'] = joined
    return {'version': version, 'source': TEST_UPDATES, 'page_last_reviewed': reviewed,
            'fetched': dt.datetime.now().astimezone().isoformat(timespec='minutes'), 'items': items}


def current_senators(state):
    st = state.upper()
    if st == 'DC' or st in TERRITORIES:
        return {'state': st, 'senators': [], 'answer': 'D.C. or the territory where you live has no U.S. senators (official answer note).',
                'source': 'https://www.uscis.gov/citizenship/testupdates'}
    root = ET.fromstring(fetch('https://www.senate.gov/general/contact_information/senators_cfm.xml'))
    sen = [f"{m.findtext('first_name').strip()} {m.findtext('last_name').strip()}"
           for m in root.iter('member') if (m.findtext('state') or '').strip() == st]
    if not sen:
        raise SystemExit(f'No senators found for {st}. Send the owner to https://www.senate.gov/senators/senators-contact.htm')
    return {'state': st, 'senators': sen, 'source': 'https://www.senate.gov/senators/senators-contact.htm',
            'fetched': dt.datetime.now().astimezone().isoformat(timespec='minutes')}


def current_governor(state):
    st = state.upper() if len(state) == 2 else next((k for k, v in STATES.items() if v == state.lower().replace(' ', '-')), None)
    if not st:
        raise SystemExit('unknown state ' + state)
    if st == 'DC':
        return {'state': 'DC', 'governor': None, 'answer': 'D.C. does not have a governor (official answer note).'}
    url = f'https://www.usa.gov/states/{STATES[st]}'
    lines = text_of(fetch(url))
    gov = None
    for i, l in enumerate(lines):
        m = re.match(r'^(?:Contact )?Governor\s+(.+)$', l)
        if m and not re.match(r'^(?:Contact )?Governor (?:of|\'s)', l):
            gov = m.group(1).strip(); break
    if not gov:
        raise SystemExit(f'Governor not found on {url}. Send the owner to https://www.usa.gov/states-and-territories')
    return {'state': st, 'governor': gov, 'source': url, 'fetched': dt.datetime.now().astimezone().isoformat(timespec='minutes')}


def current_capital(state):
    st = state.upper()
    if st == 'DC':
        return {'state': 'DC', 'capital': None, 'answer': 'D.C. is not a state and does not have a capital (official answer note).'}
    caps = json.loads((ROOT / 'data' / 'capitals.json').read_text())
    return {'state': st, 'capital': caps['capitals'][st], 'note': caps['note'], 'sources': caps['sources']}


def current_representative(state, district=None):
    st = state.upper()
    root = ET.fromstring(fetch('https://clerk.house.gov/xml/lists/MemberData.xml'))
    published = root.get('publish-date')
    rows = []
    for m in root.iter('member'):
        sd = m.findtext('statedistrict') or ''
        if not sd.startswith(st):
            continue
        info = m.find('member-info')
        name = (info.findtext('official-name') or '').strip()
        rows.append({'district': sd[2:].lstrip('0') or 'At large', 'name': name or 'Vacant'})
    if district:
        want = str(district).lstrip('0') or 'At large'
        rows = [r for r in rows if r['district'] == want or (want.lower() in ('at large', 'al') and r['district'] == 'At large')]
    return {'state': st, 'members': rows, 'list_published': published,
            'source': 'https://clerk.house.gov/Members', 'find_by_zip': 'https://www.house.gov/representatives/find-your-representative',
            'fetched': dt.datetime.now().astimezone().isoformat(timespec='minutes')}


# ------------------------------------------------------------------ validation
def validate():
    data = load()
    errs = []
    for v, exp in (('2025', 128), ('2008', 100)):
        qs = deck(v)
        if len(qs) != exp:
            errs.append(f'{v}: {len(qs)} questions, expected {exp}')
        if [q['number'] for q in qs] != list(range(1, exp + 1)):
            errs.append(f'{v}: numbering is not 1..{exp}')
        if len(deck(v, True)) != 20:
            errs.append(f'{v}: 65/20 set has {len(deck(v, True))}, expected 20')
        for q in qs:
            if not q['answers']:
                errs.append(q['id'] + ' has no answers')
            if q['flags']['changes_over_time'] and not q['current_answer_key']:
                errs.append(q['id'] + ' changes over time but has no lookup key')
    std = {x['code'] for x in json.loads((ROOT / 'data' / 'standards.json').read_text())['standards']}
    for q in data['questions']:
        for code in q.get('standards', []):
            if code not in std:
                errs.append(f"{q['id']} tag {code} not in standards.json")
    for k in RULES.values():
        if not (k['pass_at'] + k['fail_at'] == k['asked'] + 1):
            errs.append(f'rule {k} stop points do not add up')
    return {'ok': not errs, 'errors': errs, 'counts': {v: i['count'] for v, i in data['versions'].items()}}


# ------------------------------------------------------------------ cli
def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    a = sp.add_parser('version'); a.add_argument('--filed'); a.add_argument('--not-filed', action='store_true')
    a = sp.add_parser('deck'); a.add_argument('--version', required=True); a.add_argument('--senior', action='store_true')
    a = sp.add_parser('init'); a.add_argument('--version', required=True); a.add_argument('--senior', action='store_true')
    a.add_argument('--daily', type=int, required=True); a.add_argument('--start', required=True)
    a.add_argument('--interview'); a.add_argument('--salt'); a.add_argument('--out', required=True)
    for name in ('today', 'stats'):
        a = sp.add_parser(name); a.add_argument('--progress', required=True); a.add_argument('--date', required=True)
    a = sp.add_parser('record'); a.add_argument('--progress', required=True); a.add_argument('--date', required=True)
    a.add_argument('--id', required=True); a.add_argument('--result', choices=['right', 'wrong'], required=True)
    a = sp.add_parser('mock'); a.add_argument('--version', required=True); a.add_argument('--senior', action='store_true'); a.add_argument('--seed', required=True)
    a = sp.add_parser('mock-score'); a.add_argument('--version', required=True); a.add_argument('--senior', action='store_true'); a.add_argument('--results', required=True)
    a.add_argument('--progress'); a.add_argument('--date')
    a = sp.add_parser('current'); a.add_argument('what', choices=['federal', 'senators', 'governor', 'representative', 'capital'])
    a.add_argument('--version', default='2025'); a.add_argument('--state'); a.add_argument('--district')
    a = sp.add_parser('log-session'); a.add_argument('--progress', required=True); a.add_argument('--date', required=True)
    a.add_argument('--minutes', type=int, required=True); a.add_argument('--kind', choices=['drill', 'mock', 'extra'], default='drill')
    a = sp.add_parser('report'); a.add_argument('--progress', required=True); a.add_argument('--date', required=True); a.add_argument('--name')
    a = sp.add_parser('snapshot'); a.add_argument('--progress', required=True)
    a = sp.add_parser('restore'); a.add_argument('--line', required=True); a.add_argument('--salt'); a.add_argument('--out', required=True)
    sp.add_parser('validate')
    x = ap.parse_args()

    if x.cmd == 'version':
        out(which_version(None if x.not_filed or not x.filed else x.filed))
    elif x.cmd == 'deck':
        out([{'id': q['id'], 'question': q['question']} for q in deck(x.version, x.senior)])
    elif x.cmd == 'init':
        p = init(x.version, x.senior, x.daily, x.start, x.interview, x.salt)
        Path(x.out).parent.mkdir(parents=True, exist_ok=True)
        Path(x.out).write_text(json.dumps(p, indent=1))
        out({'ok': True, 'questions': len(p['new_order'])})
    elif x.cmd == 'today':
        out(today(json.loads(Path(x.progress).read_text()), d(x.date)))
    elif x.cmd == 'stats':
        out(stats(json.loads(Path(x.progress).read_text()), d(x.date)))
    elif x.cmd == 'record':
        p = json.loads(Path(x.progress).read_text())
        c = record(p, d(x.date), x.id, x.result)
        Path(x.progress).write_text(json.dumps(p, indent=1))
        out({'id': x.id, **c})
    elif x.cmd == 'mock':
        out(mock(x.version, x.senior, x.seed))
    elif x.cmd == 'mock-score':
        s = mock_score(x.version, x.senior, x.results)
        if x.progress and s['finished']:
            p = json.loads(Path(x.progress).read_text())
            p['mocks'].append({'date': x.date, 'right': s['right'], 'wrong': s['wrong'], 'asked': s['asked'], 'passed': s['passed']})
            Path(x.progress).write_text(json.dumps(p, indent=1))
        out(s)
    elif x.cmd == 'current':
        if x.what == 'federal':
            out(current_federal(x.version))
        elif x.what == 'senators':
            out(current_senators(x.state))
        elif x.what == 'governor':
            out(current_governor(x.state))
        elif x.what == 'capital':
            out(current_capital(x.state))
        else:
            out(current_representative(x.state, x.district))
    elif x.cmd == 'log-session':
        p = json.loads(Path(x.progress).read_text())
        out(log_session(p, d(x.date), x.minutes, x.kind))
        Path(x.progress).write_text(json.dumps(p, indent=1))
    elif x.cmd == 'report':
        print(report(json.loads(Path(x.progress).read_text()), d(x.date), x.name), end='')
    elif x.cmd == 'snapshot':
        print(snapshot(json.loads(Path(x.progress).read_text())))
    elif x.cmd == 'restore':
        p = restore(x.line, x.salt)
        Path(x.out).parent.mkdir(parents=True, exist_ok=True)
        Path(x.out).write_text(json.dumps(p, indent=1))
        out({'ok': True, 'cards_restored': len(p['cards'])})
    elif x.cmd == 'validate':
        r = validate(); out(r); sys.exit(0 if r['ok'] else 1)


if __name__ == '__main__':
    main()
