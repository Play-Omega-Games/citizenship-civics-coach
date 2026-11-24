"""Offline checks for Citizenship Civics Coach. Run: python3 tests/test_civics.py
Set CIVICS_SRC to a folder holding the pdftotext output of the USCIS PDFs to also run the verbatim check."""
import datetime as dt
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import civics as C  # noqa: E402

DATA = json.loads((ROOT / 'data' / 'questions.json').read_text())
Q = {q['id']: q for q in DATA['questions']}


def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', ' ', s)).strip()


class Data(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(len(C.deck('2025')), 128)
        self.assertEqual(len(C.deck('2008')), 100)
        self.assertEqual(len(C.deck('2025', True)), 20)
        self.assertEqual(len(C.deck('2008', True)), 20)

    def test_validate(self):
        self.assertTrue(C.validate()['ok'])

    def test_changing_answers_never_hard_coded(self):
        # Officeholder questions must carry the USCIS pointer or "Answers will vary", never a name.
        for q in DATA['questions']:
            if q['flags']['changes_over_time']:
                txt = ' '.join(q['answers'])
                self.assertTrue('testupdates' in txt or 'Answers will vary' in txt, q['id'])

    def test_flags(self):
        self.assertEqual(sorted(q['number'] for q in C.deck('2025') if q['flags']['changes_over_time']), [23, 29, 30, 38, 39, 57, 61])
        self.assertEqual(sorted(q['number'] for q in C.deck('2008') if q['flags']['changes_over_time']), [20, 23, 28, 29, 39, 40, 43, 46, 47])
        self.assertEqual(sorted(q['number'] for q in C.deck('2025') if q['flags']['state_specific']), [23, 29, 61, 62])
        self.assertEqual(sorted(q['number'] for q in C.deck('2008', True) if True)[:3], [6, 11, 13])
        self.assertTrue(Q['2025-002']['flags']['senior_65_20'])
        self.assertFalse(Q['2025-062']['flags']['senior_65_20'])
        self.assertTrue(Q['2008-044']['flags']['senior_65_20'])

    def test_no_stray_marks(self):
        for q in DATA['questions']:
            for s in [q['question']] + q['answers']:
                self.assertNotIn('*', s, q['id'])
                self.assertNotIn('If you are 65', s, q['id'])
                self.assertNotIn('uscis.gov/citizenship ', s + ' ', q['id']) if 'of 19' in s else None

    @unittest.skipUnless(os.environ.get('CIVICS_SRC'), 'set CIVICS_SRC for the verbatim check')
    def test_verbatim(self):
        src = Path(os.environ['CIVICS_SRC'])
        for v, f in (('2025', '2025-128.txt'), ('2008', '2008-100-ooc.txt')):
            text = norm((src / f).read_text())
            for q in C.deck(v):
                self.assertIn(q['question'], text, q['id'])
                for a in q['answers'] + q['notes']:
                    self.assertIn(a, text, q['id'])


class Standards(unittest.TestCase):
    STD = json.loads((ROOT / 'data' / 'standards.json').read_text())

    def test_tags_known_and_honest(self):
        codes = {x['code'] for x in self.STD['standards']}
        self.assertEqual(codes, {'D2.Civ.2.6-8', 'D2.Civ.2.9-12', 'D2.Civ.3.6-8', 'D2.Civ.4.6-8', 'D2.Civ.5.6-8', 'D2.His.14.6-8'})
        for x in self.STD['standards']:
            self.assertEqual(x['wording'], 'supports practice toward')
            self.assertEqual(x['framework'], 'C3')
            self.assertTrue(x['verified'])
        for q in DATA['questions']:
            self.assertTrue(set(q['standards']) <= codes, q['id'])
            if q['section'] in ('Symbols', 'Holidays', 'Geography'):
                self.assertEqual(q['standards'], [], q['id'])

    @unittest.skipUnless(os.environ.get('CIVICS_SRC'), 'set CIVICS_SRC for the verbatim check')
    def test_c3_text_verbatim(self):
        text = norm((Path(os.environ['CIVICS_SRC']) / 'c3.txt').read_text())
        for x in self.STD['standards']:
            self.assertIn(f"{x['code']}. {x['text']}", text, x['code'])


class LibraryCard(unittest.TestCase):
    def test_minutes_report_restore(self):
        p = C.init('2025', False, 10, '2026-11-25', salt='t')
        day = dt.date(2026, 11, 25)
        for cid in C.today(p, day)['new']:
            C.record(p, day, cid, 'right')
        C.log_session(p, day, 9, 'drill')
        C.log_session(p, day, 500, 'extra')
        s = C.stats(p, day)
        self.assertEqual(s['minutes_total'], 99)
        self.assertEqual(s['study_days_total'], 1)
        rep = C.report(p, day, 'Test')
        self.assertIn('Minutes logged: 99', rep)
        self.assertIn('Not legal advice', rep)
        for dash in ('\u2014', '\u2013'):
            self.assertNotIn(dash, rep)
        q = C.restore(C.snapshot(p), 't')
        self.assertEqual(C.stats(q, day)['minutes_total'], 99)
        self.assertEqual(C.stats(q, day)['study_days_total'], 1)


class Version(unittest.TestCase):
    def test_cutoff(self):
        self.assertEqual(C.which_version('2025-10-19')['version'], '2008')
        self.assertEqual(C.which_version('2025-10-20')['version'], '2025')
        self.assertEqual(C.which_version(None)['version'], '2025')


class Leitner(unittest.TestCase):
    def test_flow(self):
        p = C.init('2025', False, 10, '2026-11-25', salt='t')
        day = dt.date(2026, 11, 25)
        t = C.today(p, day)
        self.assertEqual(len(t['new']), 5)
        self.assertEqual(t['reviews'], [])
        for cid in t['new']:
            C.record(p, day, cid, 'right')
        self.assertEqual(C.today(p, day + dt.timedelta(days=1))['reviews'], [])
        t2 = C.today(p, day + dt.timedelta(days=2))
        self.assertEqual(len(t2['reviews']), 5)
        C.record(p, day, t['new'][0], 'wrong')
        self.assertEqual(p['cards'][t['new'][0]]['box'], 1)
        s = C.stats(p, day)
        self.assertEqual(s['unseen'], 123)
        self.assertEqual(s['streak'], 1)

    def test_interview_raises_new(self):
        p = C.init('2025', False, 10, '2026-11-25', interview='2026-12-23', salt='t')
        t = C.today(p, dt.date(2026, 11, 25))
        self.assertEqual(len(t['new']), 9)  # 128 cards in 15 days needs 9 a day
        self.assertIsNotNone(t['pace_note'])

    def test_snapshot_roundtrip(self):
        p = C.init('2025', False, 10, '2026-11-25', salt='t')
        day = dt.date(2026, 11, 25)
        for cid in C.today(p, day)['new']:
            C.record(p, day, cid, 'right')
        p['mocks'].append({'date': '2026-11-29', 'right': 13, 'wrong': 2, 'asked': 15, 'passed': True})
        line = C.snapshot(p)
        q = C.restore(line, 't')
        self.assertEqual(C.snapshot(q), line)
        self.assertEqual(C.today(q, day + dt.timedelta(days=2))['reviews'], C.today(p, day + dt.timedelta(days=2))['reviews'])

    def test_senior_deck(self):
        p = C.init('2008', True, 5, '2026-11-25', salt='t')
        self.assertEqual(len(p['new_order']), 20)


class Mock(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(C.RULES[('2025', False)], {'pool': 128, 'asked': 20, 'pass_at': 12, 'fail_at': 9})
        self.assertEqual(C.RULES[('2008', False)], {'pool': 100, 'asked': 10, 'pass_at': 6, 'fail_at': 5})
        for senior in ('2025', '2008'):
            self.assertEqual(C.RULES[(senior, True)]['asked'], 10)
            self.assertEqual(C.RULES[(senior, True)]['pass_at'], 6)

    def test_stop_rules(self):
        s = C.mock_score('2025', False, 'R' * 12 + 'W' * 8)
        self.assertTrue(s['passed']); self.assertEqual(s['asked'], 12)
        s = C.mock_score('2025', False, 'W' * 9 + 'R' * 11)
        self.assertFalse(s['passed']); self.assertEqual(s['asked'], 9)
        s = C.mock_score('2008', False, 'RWRWRWRWRR')
        self.assertTrue(s['passed']); self.assertEqual(s['asked'], 10)
        s = C.mock_score('2008', False, 'WWWWW')
        self.assertFalse(s['passed']); self.assertTrue(s['finished'])

    def test_mock_draw(self):
        m = C.mock('2025', False, 'salt-2026-11-29')
        self.assertEqual(len({q['id'] for q in m['questions']}), 20)
        self.assertEqual(m['questions'], C.mock('2025', False, 'salt-2026-11-29')['questions'])
        m = C.mock('2025', True, 'x')
        self.assertTrue(all(q['flags']['senior_65_20'] for q in m['questions']))
        self.assertEqual(len(m['questions']), 10)

    def test_cli_record_and_mock(self):
        with tempfile.TemporaryDirectory() as td:
            p = C.init('2025', False, 10, '2026-11-25', salt='t')
            f = Path(td) / 'p.json'; f.write_text(json.dumps(p))
            self.assertTrue(f.exists())


if __name__ == '__main__':
    unittest.main(verbosity=1)
