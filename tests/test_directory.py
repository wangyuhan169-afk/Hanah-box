import json,unittest
from pathlib import Path
from collector import read_document,recruitment_links

ROOT=Path(__file__).resolve().parents[1]

class DirectoryTests(unittest.TestCase):
    def test_official_roster_is_unique_and_complete_for_its_date(self):
        roster=json.loads((ROOT/'data/guangdong_institutions.json').read_text(encoding='utf-8'))
        rows=roster['schools']
        self.assertEqual(len(rows),167)
        self.assertEqual(len({r['code'] for r in rows}),167)
        self.assertEqual(sum(r['school_level']=='本科' for r in rows),77)
        self.assertEqual(sum(r['school_level']=='专科' for r in rows),90)
        self.assertEqual(sum(r['nature']=='民办' for r in rows),52)
        self.assertIn('深圳信息职业技术学院',next(r for r in rows if r['name']=='深圳信息职业技术大学')['aliases'])

    def test_bilingual_official_job_link_is_not_silently_skipped(self):
        page=b'<html><a href="/zh-hans/recruitment/20281">Executive Assistant (Ref. 2026/198/01)</a><a href="https://example.com/zh-hans/recruitment/1">Assistant (Ref. 2026/1)</a><a href="/zh-hans/recruitment/2">Campus map</a></html>'
        doc=read_document(page,'https://www.cuhk.edu.cn/zh-hans/taxonomy/term/37')
        links=recruitment_links(doc)
        self.assertEqual([u for u,t in links],['https://www.cuhk.edu.cn/zh-hans/recruitment/20281'])

    def test_reviewed_positions_do_not_invent_dates_or_unrestricted_majors(self):
        jobs=json.loads((ROOT/'data/reviewed_positions.json').read_text(encoding='utf-8'))
        self.assertEqual(len({j['id'] for j in jobs}),len(jobs))
        for j in jobs:
            self.assertIsNone(j['opens'])
            self.assertNotIn('不限',j['majors'])
            self.assertTrue(j['source_url'].startswith('https://'))
            if 'cuhk.edu.cn' in j['source_url']:
                self.assertEqual(j['deadline'],'2026-10-31')
                self.assertIsNone(j['published'])

    def test_urgent_and_age_exception_positions_preserve_original_limits(self):
        jobs=json.loads((ROOT/'data/reviewed_positions.json').read_text(encoding='utf-8'))
        urgent=next(j for j in jobs if j['id']=='manual-gdufs-20261014-business')
        self.assertEqual(urgent['count'],3)
        self.assertEqual(urgent['deadline'],'2026-10-14')
        self.assertEqual(urgent['eligibility']['age_as_of'],'2026-10-14')
        self.assertIn('文案撰写',urgent['exam'])
        media=[j for j in jobs if j['id'].startswith('manual-gzhsvc-')]
        self.assertEqual(len(media),2)
        self.assertTrue(all(j['count'] is None and j['deadline'] is None for j in media))
        self.assertTrue(all('放宽' in j['eligibility']['age_text'] for j in media))

if __name__=='__main__':unittest.main()
