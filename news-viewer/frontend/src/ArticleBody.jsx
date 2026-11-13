import React from "react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

const SAFE_PROTOCOLS = /^(https?|mailto|tel):/i;

export function isSafeUrl(url) {
  if (!url) return false;
  const trimmed = url.trim();
  if (trimmed.startsWith("/") || trimmed.startsWith("#")) return true;
  return SAFE_PROTOCOLS.test(trimmed);
}

export function safeUrlTransform(url) {
  if (isSafeUrl(url)) return url;
  return "";
}

export const cleanArticleText = (text = "") => {
  if (!text) return "";
  const lines = text.split(/\r?\n/);
  const filtered = lines.filter((line) => !line.includes("광고"));
  return filtered
    .map((line) => line.trimEnd())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
};

const s = {
  container: {
    fontSize: 15,
    lineHeight: 1.85,
    color: "#374151",
    overflowWrap: "anywhere",
    maxWidth: "68ch",
    marginBottom: 28,
  },
  h1: {
    fontSize: 20,
    fontWeight: 700,
    lineHeight: 1.4,
    margin: "24px 0 12px",
    color: "#0f172a",
    letterSpacing: "-0.2px",
    textWrap: "balance",
  },
  h2: {
    fontSize: 18,
    fontWeight: 700,
    lineHeight: 1.45,
    margin: "20px 0 10px",
    color: "#0f172a",
    letterSpacing: "-0.2px",
    textWrap: "balance",
  },
  h3: {
    fontSize: 16,
    fontWeight: 600,
    lineHeight: 1.5,
    margin: "18px 0 8px",
    color: "#111827",
    textWrap: "balance",
  },
  h4: {
    fontSize: 15,
    fontWeight: 600,
    lineHeight: 1.5,
    margin: "16px 0 8px",
    color: "#111827",
  },
  h5: {
    fontSize: 14,
    fontWeight: 600,
    lineHeight: 1.5,
    margin: "14px 0 6px",
    color: "#111827",
  },
  h6: {
    fontSize: 13,
    fontWeight: 600,
    lineHeight: 1.5,
    margin: "12px 0 6px",
    color: "#4b5563",
    textTransform: "uppercase",
  },
  p: {
    margin: "0 0 16px",
    lineHeight: 1.85,
    textWrap: "pretty",
  },
  strong: {
    fontWeight: 600,
    color: "#111827",
  },
  em: {
    fontStyle: "italic",
  },
  ul: {
    margin: "0 0 16px",
    paddingLeft: 22,
    listStyleType: "disc",
  },
  ol: {
    margin: "0 0 16px",
    paddingLeft: 22,
    listStyleType: "decimal",
  },
  li: {
    margin: "4px 0",
    lineHeight: 1.75,
  },
  blockquote: {
    margin: "16px 0",
    padding: "10px 16px",
    borderLeft: "3px solid #7ea386",
    background: "#f5f8f5",
    borderRadius: 4,
    color: "#3e4d42",
    fontStyle: "normal",
  },
  pre: {
    margin: "16px 0",
    padding: "14px 16px",
    borderRadius: 8,
    background: "#1c261e",
    color: "#f2f7f3",
    overflowX: "auto",
    maxWidth: "100%",
    fontSize: 13.5,
    lineHeight: 1.6,
    boxSizing: "border-box",
  },
  codeBlock: {
    fontFamily:
      'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
    fontSize: "inherit",
    color: "inherit",
    background: "transparent",
    padding: 0,
    borderRadius: 0,
  },
  codeInline: {
    fontFamily:
      'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
    fontSize: "0.9em",
    color: "#16241a",
    background: "#eef3ef",
    padding: "2px 6px",
    borderRadius: 4,
    wordBreak: "break-word",
    overflowWrap: "anywhere",
  },
  link: {
    color: "#258347",
    fontWeight: 500,
    textDecoration: "underline",
    textUnderlineOffset: "3px",
    wordBreak: "break-word",
    overflowWrap: "anywhere",
  },
  disabledLink: {
    color: "inherit",
    textDecoration: "none",
    wordBreak: "break-word",
    overflowWrap: "anywhere",
  },
  img: {
    maxWidth: "100%",
    height: "auto",
    display: "block",
    margin: "16px auto",
    borderRadius: 8,
    boxSizing: "border-box",
  },
  hr: {
    border: "none",
    borderTop: "1px solid #e4e8e4",
    margin: "24px 0",
  },
  tableWrapper: {
    overflowX: "auto",
    maxWidth: "100%",
    margin: "16px 0",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 14,
    textAlign: "left",
  },
  th: {
    border: "1px solid #e4e8e4",
    padding: "8px 12px",
    background: "#f5f8f5",
    fontWeight: 600,
    color: "#16241a",
  },
  td: {
    border: "1px solid #e4e8e4",
    padding: "8px 12px",
    color: "#28382c",
  },
  empty: {
    color: "inherit",
    whiteSpace: "normal",
  },
};

export default function ArticleBody({ content, style }) {
  const cleaned = cleanArticleText(content);

  const containerStyle = {
    ...s.container,
    ...style,
    whiteSpace: "normal",
  };

  if (!cleaned) {
    return (
      <div style={{ ...containerStyle, ...s.empty }}>
        이 기사는 원문 본문을 가져오지 못했습니다.
      </div>
    );
  }

  const pStyle = {
    ...s.p,
    ...(style?.fontSize ? { fontSize: style.fontSize } : {}),
    ...(style?.lineHeight ? { lineHeight: style.lineHeight } : {}),
    ...(style?.color ? { color: style.color } : {}),
  };

  const liStyle = {
    ...s.li,
    ...(style?.fontSize ? { fontSize: style.fontSize } : {}),
    ...(style?.lineHeight ? { lineHeight: style.lineHeight } : {}),
    ...(style?.color ? { color: style.color } : {}),
  };

  const components = {
    h1: ({ node, children, ...props }) => <h1 style={s.h1} {...props}>{children}</h1>,
    h2: ({ node, children, ...props }) => <h2 style={s.h2} {...props}>{children}</h2>,
    h3: ({ node, children, ...props }) => <h3 style={s.h3} {...props}>{children}</h3>,
    h4: ({ node, children, ...props }) => <h4 style={s.h4} {...props}>{children}</h4>,
    h5: ({ node, children, ...props }) => <h5 style={s.h5} {...props}>{children}</h5>,
    h6: ({ node, children, ...props }) => <h6 style={s.h6} {...props}>{children}</h6>,
    p: ({ node, children, ...props }) => <p style={pStyle} {...props}>{children}</p>,
    strong: ({ node, children, ...props }) => <strong style={s.strong} {...props}>{children}</strong>,
    em: ({ node, children, ...props }) => <em style={s.em} {...props}>{children}</em>,
    ul: ({ node, children, ...props }) => <ul style={s.ul} {...props}>{children}</ul>,
    ol: ({ node, children, ...props }) => <ol style={s.ol} {...props}>{children}</ol>,
    li: ({ node, children, ...props }) => <li style={liStyle} {...props}>{children}</li>,
    blockquote: ({ node, children, ...props }) => (
      <blockquote style={s.blockquote} {...props}>{children}</blockquote>
    ),
    pre: ({ node, children, ...props }) => (
      <pre style={s.pre} {...props}>
        {React.isValidElement(children)
          ? React.cloneElement(children, { isBlock: true })
          : children}
      </pre>
    ),
    code: ({ node, className, isBlock, children, ...props }) => {
      const isCodeBlock = isBlock || Boolean(className);
      return (
        <code
          style={isCodeBlock ? s.codeBlock : s.codeInline}
          className={className}
          {...props}
        >
          {children}
        </code>
      );
    },
    a: ({ node, href, children, ...props }) => {
      if (!href || !isSafeUrl(href)) {
        return <span style={s.disabledLink}>{children}</span>;
      }
      const isExternal =
        href.startsWith("http://") ||
        href.startsWith("https://") ||
        href.startsWith("//");
      return (
        <a
          href={href}
          target={isExternal ? "_blank" : undefined}
          rel={isExternal ? "noopener noreferrer" : undefined}
          style={s.link}
          {...props}
        >
          {children}
        </a>
      );
    },
    img: ({ node, src, alt, ...props }) => (
      <img
        src={src}
        alt={alt || ""}
        style={s.img}
        loading="lazy"
        {...props}
      />
    ),
    hr: ({ node, ...props }) => <hr style={s.hr} {...props} />,
    table: ({ node, children, ...props }) => (
      <div style={s.tableWrapper}>
        <table style={s.table} {...props}>
          {children}
        </table>
      </div>
    ),
    th: ({ node, children, ...props }) => <th style={s.th} {...props}>{children}</th>,
    td: ({ node, children, ...props }) => <td style={s.td} {...props}>{children}</td>,
  };

  return (
    <div style={containerStyle}>
      <ReactMarkdown
        remarkPlugins={[remarkBreaks, remarkGfm]}
        urlTransform={safeUrlTransform}
        components={components}
      >
        {cleaned}
      </ReactMarkdown>
    </div>
  );
}
