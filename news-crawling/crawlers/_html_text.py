"""피드 본문(HTML)을 구조를 보존한 일반 텍스트로 변환하는 공통 헬퍼."""

import re
from typing import Any

from bs4 import BeautifulSoup
from bs4.element import NavigableString, PreformattedString, Tag

_BULLET = "•"
_INDENT = "  "

_SKIP_TAGS = {"script", "style", "noscript", "template", "head", "title", "iframe"}
_LIST_TAGS = {"ul", "ol", "menu", "dl"}
_LIST_ITEM_TAGS = {"li", "dt", "dd"}
_BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "body", "caption", "center",
    "details", "dialog", "div", "fieldset", "figcaption", "figure", "footer",
    "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "html", "legend",
    "main", "nav", "p", "section", "summary", "table", "tbody", "thead", "tfoot", "tr",
}
_CELL_TAGS = {"td", "th"}

# 일반 텍스트 속 "List<String>" 같은 표현을 HTML로 오인하지 않도록 알려진 태그 이름만 인정한다.
_KNOWN_TAG_NAMES = (
    _SKIP_TAGS | _LIST_TAGS | _LIST_ITEM_TAGS | _BLOCK_TAGS | _CELL_TAGS
    | {
        "a", "abbr", "b", "bdi", "bdo", "big", "br", "cite", "code", "del", "dfn",
        "em", "font", "i", "img", "ins", "kbd", "mark", "pre", "q", "s", "samp",
        "small", "span", "strike", "strong", "sub", "sup", "time", "tt", "u", "var",
        "wbr",
    }
)
_TAG_PATTERN = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)(?:\s[^<>]*)?/?>")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_SPACES_PATTERN = re.compile(r"[ \t]{2,}")
_BULLET_LINE_PATTERN = re.compile(rf"^( *){_BULLET}\s*(.*)$")


def looks_like_html(text: str) -> bool:
    """문자열에 알려진 HTML 태그로 보이는 패턴이 있는지 확인한다."""
    if not text:
        return False
    return any(
        match.group(1).lower() in _KNOWN_TAG_NAMES
        for match in _TAG_PATTERN.finditer(text)
    )


def html_to_text(html: str) -> str:
    """HTML 문자열을 목록·문단 구조를 보존한 일반 텍스트로 변환한다."""
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return _node_to_text(soup)


def feed_content_to_text(tag: Any) -> str:
    """피드의 content/summary/description 태그 하나를 일반 텍스트로 변환한다.

    - ``type="xhtml"`` 이거나 실제 자식 태그가 있으면 노드 트리를 그대로 변환한다.
    - 그 외(``type="html"``, 타입 없음, RSS description)는 ``get_text()``로 escape를
      한 번만 해제한 뒤, HTML로 보이면 다시 파싱해 변환하고 아니면 공백만 정리한다.
    """
    if tag is None:
        return ""
    content_type = str(tag.get("type", "") or "").strip().lower()
    has_child_tag = any(isinstance(child, Tag) for child in tag.children)
    if content_type == "xhtml" or has_child_tag:
        return _node_to_text(tag)

    text = tag.get_text()
    if looks_like_html(text):
        return html_to_text(text)
    return _normalize_plain_text(text)


def _node_to_text(node: Tag) -> str:
    renderer = _TextRenderer()
    renderer.render_children(node, list_depth=0, in_pre=False)
    return _finalize(renderer.output())


def _normalize_plain_text(text: str) -> str:
    lines = [_WHITESPACE_PATTERN.sub(" ", line).strip() for line in text.splitlines()]
    return _collapse_blank_lines(lines)


class _TextRenderer:
    """노드 트리를 순회하며 줄 단위 텍스트를 만든다."""

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._at_line_start = True
        self._after_bullet = False

    def output(self) -> str:
        return "".join(self._parts)

    def render_children(self, node: Tag, list_depth: int, in_pre: bool) -> None:
        for child in node.children:
            self._render(child, list_depth, in_pre)

    def _render(self, node: Any, list_depth: int, in_pre: bool) -> None:
        if isinstance(node, NavigableString):
            # 주석·CDATA 선언·DOCTYPE 등은 본문이 아니므로 제외한다.
            if isinstance(node, PreformattedString):
                return
            self._write_text(str(node), in_pre)
            return
        if not isinstance(node, Tag):
            return

        name = (node.name or "").lower()
        if name in _SKIP_TAGS:
            return
        if name == "br":
            self._hard_break()
            return
        if name == "pre":
            self._soft_break()
            self.render_children(node, list_depth, in_pre=True)
            self._soft_break()
            return
        if name in _LIST_TAGS:
            self._soft_break()
            self.render_children(node, list_depth + 1, in_pre)
            self._soft_break()
            return
        if name in _LIST_ITEM_TAGS:
            self._start_bullet(max(list_depth, 1))
            self.render_children(node, list_depth, in_pre)
            self._soft_break()
            return
        if name in _BLOCK_TAGS:
            self._soft_break()
            self.render_children(node, list_depth, in_pre)
            self._soft_break()
            return
        if name in _CELL_TAGS:
            self._write_text(" ", in_pre=False)
            self.render_children(node, list_depth, in_pre)
            self._write_text(" ", in_pre=False)
            return
        # 인라인 태그(strong, em, code, a, span 등)는 텍스트만 같은 줄에 이어 붙인다.
        self.render_children(node, list_depth, in_pre)

    def _write_text(self, text: str, in_pre: bool) -> None:
        if not in_pre:
            text = _WHITESPACE_PATTERN.sub(" ", text)
            if self._at_line_start:
                text = text.lstrip()
        if not text:
            return
        self._parts.append(text)
        self._at_line_start = text.endswith("\n")
        if text.strip():
            self._after_bullet = False

    def _hard_break(self) -> None:
        self._parts.append("\n")
        self._at_line_start = True
        self._after_bullet = False

    def _soft_break(self) -> None:
        # 블록 경계 줄바꿈: 이미 줄 시작이거나 bullet 직후라면 추가하지 않는다.
        if self._at_line_start or self._after_bullet:
            return
        self._parts.append("\n")
        self._at_line_start = True

    def _start_bullet(self, depth: int) -> None:
        if self._after_bullet:
            # 내용 없는 상위 항목 바로 아래 하위 항목이 오는 경우 빈 bullet 줄을 남기지 않는다.
            self._parts.append("\n")
        else:
            self._soft_break()
        self._parts.append(f"{_INDENT * (depth - 1)}{_BULLET} ")
        self._at_line_start = True
        self._after_bullet = True


def _finalize(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        bullet = _BULLET_LINE_PATTERN.match(line)
        if bullet:
            indent, body = bullet.groups()
            body = body.strip()
            if not body:
                continue
            lines.append(f"{indent}{_BULLET} {_collapse_spaces(body)}")
        else:
            lines.append(_collapse_spaces(line.strip()))
    return _collapse_blank_lines(lines)


def _collapse_spaces(line: str) -> str:
    # 인접한 텍스트 노드(&#32; 등)가 각각 공백을 남겨 생기는 중복 공백을 합친다.
    return _SPACES_PATTERN.sub(" ", line)


def _collapse_blank_lines(lines: list[str]) -> str:
    result: list[str] = []
    for line in lines:
        if not line and result and not result[-1]:
            continue
        result.append(line)
    return "\n".join(result).strip()
