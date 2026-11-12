import { createServer } from "vite";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

// Start Vite in SSR middleware mode to load the exact production ArticleBody.jsx
const vite = await createServer({
  server: { middlewareMode: true },
  appType: "custom",
});

const { default: ArticleBody, isSafeUrl, safeUrlTransform, cleanArticleText } =
  await vite.ssrLoadModule("./src/ArticleBody.jsx");

await vite.close();

const results = [];

function assert(condition, name, details = "") {
  if (condition) {
    results.push({ name, status: "PASS", details });
    console.log(`[PASS] ${name}`);
  } else {
    results.push({ name, status: "FAIL", details });
    console.error(`[FAIL] ${name}: ${details}`);
  }
}

console.log("=== 1. Text Cleaning & Advertisement Filtering ===");
const adText = "첫 번째 줄\n[광고] 이벤트 안내\n두 번째 줄\n\n새로운 문단\n광고 문의: 02-1234\n마지막 줄";
const cleaned = cleanArticleText(adText);
assert(!cleaned.includes("광고"), "cleanArticleText filters advertisement lines");
assert(cleaned.includes("첫 번째 줄\n두 번째 줄\n\n새로운 문단\n마지막 줄"), "cleanArticleText preserves paragraph breaks and line breaks");

console.log("=== 2. Safe URL Scheme Verification ===");
assert(isSafeUrl("https://news.ycombinator.com"), "isSafeUrl allows https");
assert(isSafeUrl("http://example.com"), "isSafeUrl allows http");
assert(isSafeUrl("mailto:editor@news.com"), "isSafeUrl allows mailto");
assert(isSafeUrl("/articles/10"), "isSafeUrl allows relative /");
assert(isSafeUrl("#section-1"), "isSafeUrl allows relative #");
assert(!isSafeUrl("javascript:alert(document.cookie)"), "isSafeUrl disarms javascript:");
assert(!isSafeUrl("data:text/html,<script>alert(1)</script>"), "isSafeUrl disarms data:");
assert(!isSafeUrl("vbscript:msgbox(1)"), "isSafeUrl disarms vbscript:");

console.log("=== 3. Security & Raw HTML / XSS Prevention ===");
const xssContent = "본문 내용 <script>alert('xss')</script> <img src=x onerror=alert(1)> <b>태그</b>";
const xssRendered = renderToStaticMarkup(React.createElement(ArticleBody, { content: xssContent }));
assert(!xssRendered.includes("<script>"), "Raw <script> tag is not executed or rendered as DOM element");
assert(!xssRendered.includes("<img"), "Raw <img> tag is not rendered as DOM element");
assert(xssRendered.includes("&lt;script&gt;") && xssRendered.includes("&lt;img"), "Raw HTML tags are safely entity-encoded as plain text");

const unsafeLinks = "[악성 링크](javascript:alert(1))\n[데이터 링크](data:text/html,abc)";
const unsafeRendered = renderToStaticMarkup(React.createElement(ArticleBody, { content: unsafeLinks }));
assert(!unsafeRendered.includes('href="javascript:'), "Malicious javascript: href is completely neutralized");
assert(!unsafeRendered.includes('href="data:'), "Malicious data: href is completely neutralized");
assert(unsafeRendered.includes("<span") && unsafeRendered.includes("악성 링크"), "Disarmed links render safe children as <span>");

const unsafeMdImg = "![악성 이미지](javascript:alert(1))";
const unsafeImgRendered = renderToStaticMarkup(React.createElement(ArticleBody, { content: unsafeMdImg }));
assert(!unsafeImgRendered.includes('src="javascript:'), "Markdown image with javascript: URL is sanitized");

console.log("=== 4. Markdown Elements & Safe Links ===");
const mdContent = "# 제목 1\n## 제목 2\n**굵게** 및 *기울임*, `inline code`\n\n> 인용구\n\n- 목록 1\n- 목록 2\n\n```python\nprint('code')\n```\n\n[안전 링크](https://example.com)";
const mdRendered = renderToStaticMarkup(React.createElement(ArticleBody, { content: mdContent }));
assert(mdRendered.includes("<h1"), "Renders <h1>");
assert(mdRendered.includes("<h2"), "Renders <h2>");
assert(mdRendered.includes("<strong") && mdRendered.includes("굵게"), "Renders <strong>");
assert(mdRendered.includes("<em") && mdRendered.includes("기울임"), "Renders <em>");
assert(mdRendered.includes("<blockquote"), "Renders <blockquote>");
assert(mdRendered.includes("<ul") && mdRendered.includes("<li"), "Renders <ul> and <li>");
assert(mdRendered.includes("<pre") && mdRendered.includes("<code"), "Renders <pre> and <code>");
assert(mdRendered.includes('target="_blank"') && mdRendered.includes('rel="noopener noreferrer"'), "External link includes target=_blank and rel=noopener noreferrer");

console.log("=== 5. Plain Text Article Line Breaks & Blank Lines ===");
const plainText = "국방부가 ... 파견했습니다.\n국방부는 ... 말했습니다.\n\n기술분석팀은 ... 구성됐습니다.";
const plainRendered = renderToStaticMarkup(React.createElement(ArticleBody, { content: plainText }));
assert(plainRendered.includes("<br/>") || plainRendered.includes("<br />"), "Plain text preserves single line breaks via <br>");
assert(plainRendered.includes("</p><p") || plainRendered.includes("</p>\n<p"), "Plain text preserves paragraph breaks via <p>");

console.log("=== 6. Image (img) Renderer & Mobile Overflow Prevention ===");
const imgContent = "![매우 긴 대체 텍스트가 들어간 이미지 설명으로 화면을 넘치지 않아야 하는 케이스입니다](https://images.unsplash.com/photo-1500000000?w=4000)";
const imgRendered = renderToStaticMarkup(React.createElement(ArticleBody, { content: imgContent }));
assert(imgRendered.includes("<img"), "Renders <img> tag");
assert(imgRendered.includes("max-width:100%"), "Image style includes max-width: 100% to prevent overflow");
assert(imgRendered.includes("height:auto"), "Image style includes height: auto to maintain aspect ratio");
assert(imgRendered.includes('loading="lazy"'), "Image has loading=lazy");
assert(imgRendered.includes("매우 긴 대체 텍스트"), "Image preserves alt attribute");

console.log("=== 7. Typography Contract with Parent (#38 style prop inheritance) ===");
const baselineStyle = {
  fontSize: 15,
  lineHeight: 1.85,
  color: "#374151",
  whiteSpace: "pre-wrap",
  marginBottom: 28,
};
const baselineRendered = renderToStaticMarkup(
  React.createElement(ArticleBody, { content: "일반 문단 텍스트입니다.", style: baselineStyle })
);
assert(baselineRendered.includes("white-space:normal"), "Container normalizes whiteSpace to 'normal' for markdown wrapping");
assert(baselineRendered.includes("font-size:15px") || baselineRendered.includes("font-size:15"), "Paragraph respects parent style fontSize 15");
assert(baselineRendered.includes("line-height:1.85"), "Paragraph respects parent style lineHeight 1.85");

// Test Issue #38 simulated contract (17px / 1.82)
const issue38Style = {
  fontSize: 17,
  lineHeight: 1.82,
  color: "#1f2937",
  whiteSpace: "pre-wrap",
  marginBottom: 28,
};
const issue38Rendered = renderToStaticMarkup(
  React.createElement(ArticleBody, {
    content: "38번 이슈에서 전달된 문단입니다.\n\n- 목록 항목 1",
    style: issue38Style,
  })
);
assert(issue38Rendered.includes("font-size:17px") || issue38Rendered.includes("font-size:17"), "Paragraph respects #38 fontSize: 17");
assert(issue38Rendered.includes("line-height:1.82"), "Paragraph respects #38 lineHeight: 1.82");
assert(issue38Rendered.includes("color:#1f2937"), "Paragraph respects #38 color: #1f2937");
assert(issue38Rendered.includes("white-space:normal"), "Container preserves white-space: normal under #38 style");

console.log("=== 8. Empty Fallback & Contrast (#36 contract) ===");
const emptyRendered = renderToStaticMarkup(React.createElement(ArticleBody, { content: "", style: baselineStyle }));
assert(emptyRendered.includes("이 기사는 원문 본문을 가져오지 못했습니다."), "Empty fallback message rendered");
assert(!emptyRendered.includes("#9ca3af"), "Empty fallback avoids low-contrast #9ca3af");
assert(emptyRendered.includes("color:inherit"), "Empty fallback inherits body-level readable color");

const failed = results.filter((r) => r.status === "FAIL");
console.log(`\n=== Core Regression Tests: ${results.length - failed.length}/${results.length} PASSED ===`);

if (failed.length > 0) {
  process.exit(1);
}
