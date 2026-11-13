import os
import tempfile
import unittest
from bs4 import BeautifulSoup

import db
from crawlers.github_trending import _parse_row, _parse_trending


HTML_ROW_STARS_1 = """
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/example-org/ai-agent-framework">
      example-org / ai-agent-framework
    </a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">
    An innovative AI agent framework built with Python and LLMs
  </p>
  <div class="f6 color-fg-muted mt-2">
    <span class="d-inline-block ml-0 mr-3">
      <span itemprop="programmingLanguage">Python</span>
    </span>
    <a href="/example-org/ai-agent-framework/stargazers" class="Link--muted d-inline-block mr-3">
      1,234
    </a>
    <span class="d-inline-block float-sm-right">
      321 stars today
    </span>
  </div>
</article>
"""

HTML_ROW_STARS_2 = """
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/example-org/ai-agent-framework">
      example-org / ai-agent-framework
    </a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">
    An innovative AI agent framework built with Python and LLMs
  </p>
  <div class="f6 color-fg-muted mt-2">
    <span class="d-inline-block ml-0 mr-3">
      <span itemprop="programmingLanguage">Python</span>
    </span>
    <a href="/example-org/ai-agent-framework/stargazers" class="Link--muted d-inline-block mr-3">
      1,500
    </a>
    <span class="d-inline-block float-sm-right">
      400 stars today
    </span>
  </div>
</article>
"""

HTML_ROW_DIFF_DESC = """
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/example-org/ai-agent-framework">
      example-org / ai-agent-framework
    </a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">
    Completely rewritten description for this AI framework
  </p>
  <div class="f6 color-fg-muted mt-2">
    <span class="d-inline-block ml-0 mr-3">
      <span itemprop="programmingLanguage">Python</span>
    </span>
    <a href="/example-org/ai-agent-framework/stargazers" class="Link--muted d-inline-block mr-3">
      1,234
    </a>
    <span class="d-inline-block float-sm-right">
      321 stars today
    </span>
  </div>
</article>
"""


class TestGitHubTrendingStars(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        os.environ["DB_PATH"] = self.temp_db_path
        db.init_db()

    def tearDown(self):
        try:
            if os.path.exists(self.temp_db_path):
                os.remove(self.temp_db_path)
        except OSError:
            pass

    def test_parse_row_same_repo_different_stars_produces_identical_content_and_hash(self):
        """테스트 A: 별 개수만 다른 두 HTML 파싱 시 content가 동일하고 Stars가 없으며 해시가 일치한다."""
        soup1 = BeautifulSoup(HTML_ROW_STARS_1, "lxml")
        row1 = soup1.select_one("article.Box-row")
        item1 = _parse_row(row1)

        soup2 = BeautifulSoup(HTML_ROW_STARS_2, "lxml")
        row2 = soup2.select_one("article.Box-row")
        item2 = _parse_row(row2)

        self.assertIsNotNone(item1)
        self.assertIsNotNone(item2)

        # content가 같아야 함
        self.assertEqual(item1["content"], item2["content"])

        # Stars 문자열이 본문에 포함되지 않아야 함
        self.assertNotIn("Stars", item1["content"])
        self.assertNotIn("Stars", item2["content"])

        # compute_content_hash가 같아야 함
        hash1 = db.compute_content_hash(item1["title"], item1["content"])
        hash2 = db.compute_content_hash(item2["title"], item2["content"])
        self.assertEqual(hash1, hash2)

    def test_parse_trending_same_repo_different_stars(self):
        """테스트 A 확장: _parse_trending을 통해서도 동일하게 별 개수 무관하게 해시가 일치한다."""
        trending_html_1 = f"<html><body>{HTML_ROW_STARS_1}</body></html>"
        trending_html_2 = f"<html><body>{HTML_ROW_STARS_2}</body></html>"

        items1 = _parse_trending(trending_html_1)
        items2 = _parse_trending(trending_html_2)

        self.assertEqual(len(items1), 1)
        self.assertEqual(len(items2), 1)
        self.assertEqual(items1[0]["content"], items2[0]["content"])
        self.assertNotIn("Stars", items1[0]["content"])
        self.assertNotIn("Stars", items2[0]["content"])

        hash1 = db.compute_content_hash(items1[0]["title"], items1[0]["content"])
        hash2 = db.compute_content_hash(items2[0]["title"], items2[0]["content"])
        self.assertEqual(hash1, hash2)

    def test_different_description_produces_different_hash(self):
        """테스트 B: 설명만 다른 HTML은 본문 및 제목 해시가 다르다."""
        soup1 = BeautifulSoup(HTML_ROW_STARS_1, "lxml")
        row1 = soup1.select_one("article.Box-row")
        item1 = _parse_row(row1)

        soup3 = BeautifulSoup(HTML_ROW_DIFF_DESC, "lxml")
        row3 = soup3.select_one("article.Box-row")
        item3 = _parse_row(row3)

        self.assertIsNotNone(item1)
        self.assertIsNotNone(item3)

        hash1 = db.compute_content_hash(item1["title"], item1["content"])
        hash3 = db.compute_content_hash(item3["title"], item3["content"])
        self.assertNotEqual(hash1, hash3)

    def test_completed_translation_preserved_on_refresh_with_different_stars(self):
        """테스트 C: 완료 번역 재사용 검증
        1. 기사 저장
        2. 해당 해시로 번역 완료 처리 (get_or_create_translation + complete_article_translation)
        3. 별 개수만 바뀐 파싱 결과로 refresh_article_from_source 호출
        4. 갱신 후 DB의 제목·본문 해시가 완료 번역의 해시와 같음을 확인하고 완료 상태 레코드 존재 확인
        """
        soup1 = BeautifulSoup(HTML_ROW_STARS_1, "lxml")
        item1 = _parse_row(soup1.select_one("article.Box-row"))
        self.assertIsNotNone(item1)

        # 1. 기사 저장
        saved = db.save_article(item1)
        self.assertTrue(saved)
        article_id = db.get_article_id_by_url(item1["url"])
        self.assertIsNotNone(article_id)

        # 2. 해당 해시로 번역 완료 처리
        original_hash = db.compute_content_hash(item1["title"], item1["content"])
        trans = db.get_or_create_translation(article_id, original_hash)
        self.assertEqual(trans["status"], "pending")

        completed = db.complete_article_translation(
            article_id=article_id,
            content_hash=original_hash,
            translated_title="테스트 AI 프레임워크",
            translated_content="Python과 LLM으로 구축된 혁신적인 AI 에이전트 프레임워크",
            model="gemini-2.5-flash",
        )
        self.assertTrue(completed)

        # 3. 별 개수만 바뀐 파싱 결과로 refresh_article_from_source 호출
        soup2 = BeautifulSoup(HTML_ROW_STARS_2, "lxml")
        item2 = _parse_row(soup2.select_one("article.Box-row"))
        self.assertIsNotNone(item2)

        refreshed = db.refresh_article_from_source(item2)
        self.assertTrue(refreshed)

        # 4. 갱신 후 DB 제목·본문 해시 계산
        refreshed_article = db.get_article_by_url(item1["url"])
        self.assertIsNotNone(refreshed_article)
        refreshed_hash = db.compute_content_hash(
            refreshed_article["title"],
            refreshed_article["content"],
        )

        # 갱신 후 DB 해시가 완료 번역의 해시와 동일함 확인
        self.assertEqual(refreshed_hash, original_hash)

        # 완료 상태 행 존재 확인 (대기열 재번역 트리거 없음)
        completed_trans = db.get_or_create_translation(article_id, refreshed_hash)
        self.assertEqual(completed_trans["status"], "completed")
        self.assertEqual(completed_trans["content_hash"], original_hash)
        self.assertEqual(completed_trans["translated_title"], "테스트 AI 프레임워크")


if __name__ == "__main__":
    unittest.main()
