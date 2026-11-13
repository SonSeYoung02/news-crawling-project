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

    def test_search_uses_body_and_summary(self):
        from fastapi.testclient import TestClient
        self.add(1)
        client = TestClient(main.app)
        self.assertEqual(client.get('/articles', params={'q':'본문'}).json()['total'], 1)
        self.assertEqual(client.get('/articles', params={'q':'요약'}).json()['total'], 1)
        self.assertEqual(client.get('/articles', params={'q':'없는단어'}).json()['total'], 0)

    def test_legacy_summary_does_not_affect_ranking(self):
        self.add(1, '2026-11-10T01:00:00Z')
        self.add(2, '2026-11-10T02:00:00Z')
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('UPDATE articles SET summary = NULL WHERE id = 2')
        self.assertEqual(self.result()['articles'][0]['id'], 2)

    def test_briefing_translation_priority_and_fallback(self):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('''
                CREATE TABLE article_translations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    translated_title TEXT,
                    translated_content TEXT,
                    language TEXT DEFAULT 'ko',
                    status TEXT DEFAULT 'pending',
                    attempts INTEGER DEFAULT 0,
                    completed_at TEXT,
                    model TEXT,
                    last_error TEXT,
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                )
            ''')
        self.add(10, published='2026-11-10T02:00:00Z', category='AI', source='techcrunch', topic='LLM')
        self.add(11, published='2026-11-10T02:00:00Z', category='AI', source='huggingface', topic='Vision')
        self.add(12, published='2026-11-10T02:00:00Z', category='AI', source='네이버뉴스', topic='NLP')
        self.add(13, published='2026-11-10T02:00:00Z', category='AI', source='GeekNews', topic='Dev')
        h = main.compute_content_hash('기사 10', '본문')
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('''
                INSERT INTO article_translations (article_id, content_hash, translated_title, translated_content, status)
                VALUES (10, ?, '번역된 기사 10', '번역된 본문 내용', 'completed')
            ''', (h,))
        res = self.result()
        articles_map = {a['id']: a for a in res['articles']}
        self.assertIn(10, articles_map)
        self.assertIn(11, articles_map)
        self.assertIn(12, articles_map)
        self.assertIn(13, articles_map)

        art10 = articles_map[10]
        self.assertEqual(art10['title'], '번역된 기사 10')
        self.assertEqual(art10['content'], '번역된 본문 내용')
        self.assertEqual(art10['original_title'], '기사 10')
        self.assertEqual(art10['original_content'], '본문')
        self.assertEqual(art10['translated_title'], '번역된 기사 10')
        self.assertEqual(art10['translated_content'], '번역된 본문 내용')
        self.assertEqual(art10['translation_status'], 'completed')

        art11 = articles_map[11]
        self.assertEqual(art11['title'], '기사 11')
        self.assertEqual(art11['content'], '본문')
        self.assertEqual(art11['original_title'], '기사 11')
        self.assertEqual(art11['original_content'], '본문')
        self.assertIsNone(art11['translated_title'])
        self.assertIsNone(art11['translated_content'])
        self.assertEqual(art11['translation_status'], 'pending')

        art12 = articles_map[12]
        self.assertEqual(art12['source'], '네이버뉴스')
        self.assertEqual(art12['translation_status'], 'not_needed')

        art13 = articles_map[13]
        self.assertEqual(art13['source'], 'GeekNews')
        self.assertEqual(art13['translation_status'], 'not_needed')

    def test_briefing_korean_sources_without_translation_table(self):
        # article_translations 테이블이 없는 경우
        self.add(20, published='2026-11-10T02:00:00Z', category='AI', source='네이버뉴스', topic='NLP')
        self.add(21, published='2026-11-10T02:00:00Z', category='AI', source='GeekNews', topic='Dev')
        self.add(22, published='2026-11-10T02:00:00Z', category='AI', source='huggingface', topic='Vision')
        res = self.result()
        articles_map = {a['id']: a for a in res['articles']}
        self.assertIn(20, articles_map)
        self.assertIn(21, articles_map)
        self.assertIn(22, articles_map)
        self.assertEqual(articles_map[20]['translation_status'], 'not_needed')
        self.assertEqual(articles_map[21]['translation_status'], 'not_needed')
        self.assertEqual(articles_map[22]['translation_status'], 'pending')


if __name__ == '__main__':
    unittest.main()
