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
    sys.exit(1 if bad else 0)
