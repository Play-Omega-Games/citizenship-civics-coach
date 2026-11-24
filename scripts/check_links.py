"""Check every source link the bot relies on. Run: python3 scripts/check_links.py"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINKS = [
    'https://www.uscis.gov/citizenship/testupdates',
    'https://www.uscis.gov/citizenship/find-study-materials-and-resources/check-for-test-updates',
    'https://www.uscis.gov/citizenship/find-study-materials-and-resources/study-for-the-test',
    'https://www.uscis.gov/citizenship-resource-center/naturalization-test-and-study-resources/2025-civics-test',
    'https://www.uscis.gov/citizenship/exceptions-and-accommodations',
    'https://www.uscis.gov/policy-manual/volume-12-part-e-chapter-2',
    'https://www.federalregister.gov/documents/2025/09/18/2025-18050/notice-of-implementation-of-2025-naturalization-civics-test',
    'https://www.uscis.gov/sites/default/files/document/brochures/USCIS-2025-Civics-Test-Study-Guide.pdf',
    'https://www.senate.gov/senators/senators-contact.htm',
    'https://www.senate.gov/general/contact_information/senators_cfm.xml',
    'https://www.house.gov/representatives/find-your-representative',
    'https://clerk.house.gov/Members',
    'https://clerk.house.gov/xml/lists/MemberData.xml',
    'https://www.usa.gov/states-and-territories',
    'https://www.usa.gov/state-governments',
    'https://www.bia.gov/',
]
# Next shelf card targets (x.ai/bot store pages). Checked separately: x.ai may answer bots with a challenge page.
NEXT_SHELF = ['https://x.ai/bot/OiJ2yft0AxrfrCdRAgFYu', 'https://x.ai/bot/k232Uq3GOPgOdh63JWIWp']


def all_links():
    data = json.loads((ROOT / 'data' / 'questions.json').read_text())
    caps = json.loads((ROOT / 'data' / 'capitals.json').read_text())
    std = json.loads((ROOT / 'data' / 'standards.json').read_text())
    links = (list(LINKS) + [v['source_url'] for v in data['versions'].values()] + caps['sources']
             + [x['source'] for x in std['standards']] + [x['document'] for x in std['standards']] + NEXT_SHELF)
    return list(dict.fromkeys(links))


def verify_capitals():
    """Confirm every capital in data/capitals.json appears in the official source text (needs pdftotext)."""
    import html, shutil, subprocess, tempfile, unicodedata, re
    caps = json.loads((ROOT / 'data' / 'capitals.json').read_text())
    if not shutil.which('pdftotext'):
        print('SKIP capitals content check (pdftotext not installed)')
        return 0
    with tempfile.TemporaryDirectory() as td:
        pdf = Path(td) / 'gpo.pdf'
        req = urllib.request.Request(caps['sources'][0], headers={'User-Agent': 'Mozilla/5.0'})
        pdf.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        subprocess.run(['pdftotext', str(pdf), str(pdf) + '.txt'], check=True)
        gpo = unicodedata.normalize('NFKC', (Path(str(pdf) + '.txt')).read_text())
    req = urllib.request.Request(caps['sources'][1], headers={'User-Agent': 'Mozilla/5.0'})
    nasa = unicodedata.normalize('NFKC', urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace'))
    gpo = re.sub(r'\s+', ' ', gpo)
    bad = 0
    for st, cap in caps['capitals'].items():
        names = [cap] + caps.get('also_accepted', {}).get(st, [])
        ok = any(f'({st}) ' in gpo and re.search(rf'\({st}\) \([^)]*\) Capital: {re.escape(n)}', gpo) for n in names)
        if st == 'GU':  # current name, from NASA Space Place
            ok = ok and cap in unicodedata.normalize('NFKC', html.unescape(nasa))
        if not ok:
            bad += 1
            print('BAD capital', st, cap)
    print(f'capitals: {len(caps["capitals"]) - bad}/{len(caps["capitals"])} confirmed in official sources')
    return bad


def check(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; CitizenshipCivicsCoach/1.0)'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.geturl()
    except Exception as e:  # noqa: BLE001
        return getattr(e, 'code', 'ERR'), str(e)


if __name__ == '__main__':
    bad = 0
    for u in all_links():
        code, final = check(u)
        ok = code == 200
        bad += not ok
        print('OK ' if ok else 'BAD', code, u, '' if final == u else f'-> {final}')
    print(f'{len(all_links()) - bad}/{len(all_links())} live')
    bad += verify_capitals()
    sys.exit(1 if bad else 0)
