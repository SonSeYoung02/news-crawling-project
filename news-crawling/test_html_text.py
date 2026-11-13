import re
import unittest

from bs4 import BeautifulSoup

from crawlers._html_text import feed_content_to_text, html_to_text, looks_like_html
from crawlers.geeknews import _parse_feed

_TAG_RESIDUE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*[^<>]*>")

_ICEWM_ESCAPED = (
    "&lt;div&gt;&lt;ul&gt;&lt;li&gt;&lt;strong&gt;IceWM&lt;/strong&gt;은 빠르고 단순함&lt;/li&gt;"
    "&lt;li&gt;키보드만으로도 사용 가능&lt;/li&gt;&lt;/ul&gt;&lt;hr&gt;&lt;h2&gt;창 관리&lt;/h2&gt;&lt;/div&gt;"
)
_ICEWM_EXPECTED = "• IceWM은 빠르고 단순함\n• 키보드만으로도 사용 가능\n창 관리"


def _atom_content(inner: str, attrs: str) -> object:
    xml = (
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
        f"<content {attrs}>{inner}</content>"
        "</entry></feed>"
    )
    return BeautifulSoup(xml, "lxml-xml").find("content")


class TestFeedContentToText(unittest.TestCase):
    def test_escaped_atom_html_content(self):
        tag = _atom_content(_ICEWM_ESCAPED, "type='html' xml:lang='ko'")
        result = feed_content_to_text(tag)
        self.assertEqual(result, _ICEWM_EXPECTED)
        self.assertIsNone(_TAG_RESIDUE.search(result))

    def test_xhtml_content_with_child_tags(self):
        inner = (
            '<div xmlns="http://www.w3.org/1999/xhtml">'
            '<p>Hello <a href="https://example.com">링크</a> &amp; <em>world</em></p>'
            "<ul><li>항목</li></ul></div>"
        )
        tag = _atom_content(inner, 'type="xhtml"')
        result = feed_content_to_text(tag)
        self.assertEqual(result, "Hello 링크 & world\n• 항목")
        self.assertNotIn("https://example.com", result)

    def test_double_escaped_text_is_unescaped_only_once(self):
        # 본문에 문자 그대로의 "&lt;div&gt;"가 있으면 html 타입에서 escape는 한 번만 풀린다.
        tag = _atom_content("&amp;lt;div&amp;gt; 태그 설명", "type='html'")
        self.assertEqual(feed_content_to_text(tag), "&lt;div&gt; 태그 설명")

    def test_rss_description_cdata(self):
        xml = "<rss><channel><item><description><![CDATA[<p>첫 문단</p><p>둘째 문단</p>]]></description></item></channel></rss>"
        tag = BeautifulSoup(xml, "lxml-xml").find("description")
        self.assertEqual(feed_content_to_text(tag), "첫 문단\n둘째 문단")

    def test_plain_text_unchanged(self):
        tag = _atom_content("그냥 일반 텍스트 List&lt;String&gt; 포함", "type='text'")
        self.assertEqual(feed_content_to_text(tag), "그냥 일반 텍스트 List<String> 포함")

    def test_none_tag(self):
        self.assertEqual(feed_content_to_text(None), "")


class TestHtmlToText(unittest.TestCase):
    def test_nested_list_indentation(self):
        html = "<ul><li>상위<ul><li>하위<ul><li>최하위</li></ul></li></ul></li><li>다음</li></ul>"
        self.assertEqual(html_to_text(html), "• 상위\n  • 하위\n    • 최하위\n• 다음")

    def test_ordered_list_uses_bullet(self):
        self.assertEqual(html_to_text("<ol><li>하나</li><li>둘</li></ol>"), "• 하나\n• 둘")

    def test_br_and_paragraphs(self):
        html = "<p>첫 줄<br>둘째 줄</p><p>문단 둘</p>a<br><br><br><br>b"
        self.assertEqual(html_to_text(html), "첫 줄\n둘째 줄\n문단 둘\na\n\nb")

    def test_link_text_only(self):
        html = '<p>자세한 내용은 <a href="https://example.com/x">여기</a>를 참고</p>'
        self.assertEqual(html_to_text(html), "자세한 내용은 여기를 참고")

    def test_inline_tags_stay_on_same_line(self):
        html = "<li><strong>굵게</strong>와 <em>기울임</em>, <code>code()</code> 연결</li>"
        self.assertEqual(html_to_text(html), "• 굵게와 기울임, code() 연결")

    def test_script_and_style_removed(self):
        html = "<style>p{color:red}</style><p>본문</p><script>alert(1)</script>"
        self.assertEqual(html_to_text(html), "본문")

    def test_list_item_with_paragraph_keeps_bullet_line(self):
        self.assertEqual(html_to_text("<ul><li><p>문단 항목</p></li></ul>"), "• 문단 항목")

    def test_empty_input(self):
        self.assertEqual(html_to_text(""), "")
        self.assertEqual(html_to_text("   "), "")

    def test_no_tag_residue(self):
        html = BeautifulSoup(f"<x>{_ICEWM_ESCAPED}</x>", "html.parser").get_text()
        result = html_to_text(html)
        self.assertEqual(result, _ICEWM_EXPECTED)
        self.assertIsNone(_TAG_RESIDUE.search(result))

    def test_looks_like_html(self):
        self.assertTrue(looks_like_html("<div>본문</div>"))
        self.assertTrue(looks_like_html("줄<br/>바꿈"))
        self.assertFalse(looks_like_html("List<String> 과 a < b"))
        self.assertFalse(looks_like_html(""))


class TestGeekNewsParse(unittest.TestCase):
    def test_parse_feed_strips_escaped_html(self):
        xml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
            "<title>IceWM 소개</title>"
            '<link rel="alternate" href="https://news.hada.io/topic?id=1"/>'
            "<published>2026-11-13T00:00:00+09:00</published>"
            f"<content type='html' xml:lang='ko'>{_ICEWM_ESCAPED}</content>"
            "</entry></feed>"
        )
        articles = _parse_feed(xml)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["content"], _ICEWM_EXPECTED)


if __name__ == "__main__":
    unittest.main()
