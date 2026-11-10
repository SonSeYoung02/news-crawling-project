import sqlite3
from contextlib import closing
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import main

NOW = datetime(2026, 11, 10, 3, tzinfo=timezone.utc)

class BriefingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'news.db'
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('CREATE TABLE articles (id INTEGER PRIMARY KEY, url TEXT, source TEXT, title TEXT, content TEXT, published_at TEXT, crawled_at TEXT, summary TEXT, major_category TEXT, sub_category TEXT, tags TEXT)')
            c.execute('CREATE TABLE article_analysis (article_id INTEGER, summary TEXT, major_category TEXT, sub_category TEXT, tags TEXT)')
        self.patch = patch.object(main, 'DB_PATH', self.db)
        self.patch.start()
    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()
    def add(self, i, published='2026-11-10T02:00:00Z', crawled='2026-11-10T12:00:00', category='AI', source='arXiv', topic='LLM'):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?)', (i, f'https://example.com/{i}', source, f'기사 {i}', '본문', published, crawled, '요약', category, topic, '[]'))
    def result(self):
        with patch.object(main, '_utc_now', return_value=NOW):
            return main.get_briefing()
    def test_empty(self):
        r = self.result()
        self.assertEqual(r['articles'], [])
        self.assertEqual(r['window_end'], NOW.isoformat())
        main.BriefingResponse(**r)
    def test_time_window_fallback_and_ai_only(self):
        self.add(1, '2026-11-09T03:00:00Z')
        self.add(2, '2026-11-09T02:59:59Z')
        self.add(3, None)
        self.add(4, '2026-11-10T03:00:01Z')
        self.add(5, category='IT')
        self.add(6, 'invalid', 'invalid')
        self.add(7, '2026-11-10T12:00:00')
        self.assertEqual({a['id'] for a in self.result()['articles']}, {1,3,7})
    def test_limit_diversity_and_source_metadata(self):
        for i in range(1, 8): self.add(i)
        self.add(8, source='Hugging Face', topic='로보틱스')
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('INSERT INTO article_analysis VALUES (?,?,?,?,?)', (8,'보강 요약','AI','로보틱스','["robot"]'))
        items = self.result()['articles']
        self.assertEqual(len(items), 5)
        item = next(a for a in items if a['id'] == 8)
        self.assertEqual(item['summary'], '요약')
        self.assertEqual(item['tags'], [])
        main.BriefingResponse(**self.result())
    def test_invalid_publication_uses_crawl_but_old_publication_does_not(self):
        self.add(1, 'bad')
        self.add(2, '2020-01-01T00:00:00Z')
        self.assertEqual([a['id'] for a in self.result()['articles']], [1])




    def test_http_contract(self):
        from fastapi.testclient import TestClient
        self.add(1)
        with patch.object(main, '_utc_now', return_value=NOW):
            response = TestClient(main.app).get('/briefing')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['articles']), 1)
        self.assertIn('/briefing', main.app.openapi()['paths'])
    def test_rfc_dates_and_summary_fallback(self):
        self.add(1, 'Tue, 10 Nov 2026 11:00:00 +0900')
        self.assertEqual([a['id'] for a in self.result()['articles']], [1])

    def test_search_uses_body_not_legacy_ai_summary(self):
        from fastapi.testclient import TestClient
        self.add(1)
        client = TestClient(main.app)
        self.assertEqual(client.get('/articles', params={'q':'본문'}).json()['total'], 1)
        self.assertEqual(client.get('/articles', params={'q':'요약'}).json()['total'], 0)

    def test_legacy_summary_does_not_affect_ranking(self):
        self.add(1, '2026-11-10T01:00:00Z')
        self.add(2, '2026-11-10T02:00:00Z')
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('UPDATE articles SET summary = NULL WHERE id = 2')
        self.assertEqual(self.result()['articles'][0]['id'], 2)

if __name__ == '__main__': unittest.main()

