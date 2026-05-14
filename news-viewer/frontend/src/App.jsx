import { useEffect, useState } from "react";

const API = "http://localhost:8000";

const ACCENT = "#7c3aed";
const ACCENT_LIGHT = "#ede9fe";
const ACCENT_MID = "#8b5cf6";
const BORDER = "#e5e7eb";
const TEXT_SECONDARY = "#6b7280";
const TEXT_MUTED = "#9ca3af";
const CATEGORY_FILTERS = ["경제", "IT", "기타"];
const SOURCE_FILTERS = ["네이버뉴스", "조선일보", "한겨레", "Google News", "arXiv", "dev.to"];

const cleanArticleText = (text = "") =>
  text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.includes("\uad11\uace0"))
    .join("\n");

const s = {
  layout: {
    display: "flex",
    height: "100vh",
    overflow: "hidden",
    background: "#f8fafc",
  },
  sidebar: {
    width: 240,
    background: "#ffffff",
    borderRight: `1px solid ${BORDER}`,
    display: "flex",
    flexDirection: "column",
    flexShrink: 0,
  },
  sidebarHeader: {
    padding: "20px 20px 16px",
    borderBottom: `1px solid ${BORDER}`,
  },
  sidebarTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: ACCENT,
    letterSpacing: "-0.3px",
  },
  sidebarSubtitle: {
    fontSize: 11,
    color: TEXT_MUTED,
    marginTop: 2,
  },
  sidebarScroll: {
    flex: 1,
    overflowY: "auto",
    padding: "16px 12px",
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: TEXT_MUTED,
    textTransform: "uppercase",
    letterSpacing: "0.6px",
    padding: "0 8px",
    marginBottom: 6,
    marginTop: 16,
  },
  filterItem: (active) => ({
    padding: "7px 10px",
    borderRadius: 8,
    cursor: "pointer",
    marginBottom: 2,
    background: active ? ACCENT_LIGHT : "transparent",
    color: active ? ACCENT : "#374151",
    fontWeight: active ? 600 : 400,
    fontSize: 14,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    transition: "background 0.15s",
  }),
  filterCount: (active) => ({
    fontSize: 11,
    color: active ? ACCENT_MID : TEXT_MUTED,
    fontWeight: 500,
  }),
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  topbar: {
    padding: "14px 20px",
    borderBottom: `1px solid ${BORDER}`,
    background: "#ffffff",
    display: "flex",
    gap: 10,
    alignItems: "center",
  },
  searchInput: {
    flex: 1,
    padding: "9px 14px",
    borderRadius: 10,
    border: `1.5px solid ${BORDER}`,
    fontSize: 14,
    outline: "none",
    background: "#f9fafb",
    transition: "border-color 0.15s",
  },
  searchBtn: {
    padding: "9px 20px",
    borderRadius: 10,
    background: ACCENT,
    color: "#fff",
    border: "none",
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 600,
    letterSpacing: "0.2px",
    flexShrink: 0,
  },
  content: {
    flex: 1,
    display: "flex",
    overflow: "hidden",
  },
  listPanel: {
    width: 400,
    overflowY: "auto",
    borderRight: `1px solid ${BORDER}`,
    background: "#f8fafc",
    padding: "12px 12px",
  },
  card: (selected) => ({
    padding: "14px 16px",
    borderRadius: 12,
    marginBottom: 8,
    cursor: "pointer",
    background: selected ? "#ffffff" : "#ffffff",
    border: `1.5px solid ${selected ? ACCENT : BORDER}`,
    boxShadow: selected
      ? `0 0 0 3px ${ACCENT_LIGHT}`
      : "0 1px 3px rgba(0,0,0,0.05)",
    transition: "border-color 0.15s, box-shadow 0.15s",
  }),
  cardMeta: {
    fontSize: 12,
    color: ACCENT,
    fontWeight: 500,
    marginBottom: 5,
    display: "flex",
    gap: 6,
    alignItems: "center",
  },
  cardDot: {
    width: 3,
    height: 3,
    borderRadius: "50%",
    background: ACCENT_MID,
    flexShrink: 0,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: 600,
    lineHeight: 1.45,
    marginBottom: 7,
    color: "#111827",
  },
  cardSummary: {
    fontSize: 12.5,
    color: TEXT_SECONDARY,
    lineHeight: 1.5,
    marginBottom: 8,
  },
  tagRow: {
    display: "flex",
    gap: 4,
    flexWrap: "wrap",
  },
  tag: {
    fontSize: 11,
    background: ACCENT_LIGHT,
    color: ACCENT,
    padding: "2px 9px",
    borderRadius: 20,
    fontWeight: 500,
  },
  pagination: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    gap: 10,
    padding: "16px 0 8px",
  },
  pageBtn: (disabled) => ({
    padding: "6px 16px",
    borderRadius: 8,
    border: `1.5px solid ${BORDER}`,
    background: disabled ? "#f3f4f6" : "#ffffff",
    color: disabled ? TEXT_MUTED : "#374151",
    cursor: disabled ? "default" : "pointer",
    fontSize: 13,
    fontWeight: 500,
  }),
  pageInfo: {
    fontSize: 13,
    color: TEXT_SECONDARY,
    minWidth: 60,
    textAlign: "center",
  },
  detailPanel: {
    flex: 1,
    overflowY: "auto",
    padding: "32px 40px",
    background: "#ffffff",
  },
  detailEmpty: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    height: "100%",
    color: TEXT_MUTED,
    gap: 8,
  },
  detailEmptyIcon: {
    fontSize: 40,
    opacity: 0.3,
  },
  detailMeta: {
    fontSize: 12,
    color: ACCENT,
    fontWeight: 500,
    marginBottom: 12,
    display: "flex",
    gap: 8,
    alignItems: "center",
    flexWrap: "wrap",
  },
  detailTitle: {
    fontSize: 22,
    fontWeight: 700,
    lineHeight: 1.4,
    marginBottom: 14,
    color: "#0f172a",
    letterSpacing: "-0.3px",
  },
  detailDate: {
    fontSize: 12,
    color: TEXT_MUTED,
    marginBottom: 24,
    display: "flex",
    gap: 8,
    alignItems: "center",
  },
  detailLink: {
    color: ACCENT,
    fontWeight: 500,
  },
  summaryBox: {
    background: ACCENT_LIGHT,
    border: `1px solid #ddd6fe`,
    borderLeft: `4px solid ${ACCENT}`,
    borderRadius: 10,
    padding: "14px 18px",
    marginBottom: 24,
  },
  summaryLabel: {
    fontSize: 11,
    color: ACCENT,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.5px",
    marginBottom: 8,
  },
  summaryText: {
    fontSize: 14,
    lineHeight: 1.75,
    color: "#374151",
  },
  detailContent: {
    fontSize: 15,
    lineHeight: 1.85,
    color: "#374151",
    whiteSpace: "pre-wrap",
    marginBottom: 28,
  },
  statusText: {
    textAlign: "center",
    color: TEXT_MUTED,
    padding: "40px 0",
    fontSize: 14,
  },
};

export default function App() {
  const [articles, setArticles] = useState([]);
  const [categories, setCategories] = useState([]);
  const [sources, setSources] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedSource, setSelectedSource] = useState("");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);

  const SIZE = 20;

  useEffect(() => {
    fetch(`${API}/categories`).then((r) => r.json()).then(setCategories);
    fetch(`${API}/sources`).then((r) => r.json()).then(setSources);
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({ page, size: SIZE });
    if (selectedCategory) params.set("category", selectedCategory);
    if (selectedSource) params.set("source", selectedSource);
    if (search) params.set("q", search);
    fetch(`${API}/articles?${params}`)
      .then((r) => r.json())
      .then((data) => {
        setArticles(data.articles);
        setTotal(data.total);
      })
      .finally(() => setLoading(false));
  }, [page, selectedCategory, selectedSource, search]);

  useEffect(() => {
    if (!loading && !selected && articles.length > 0) {
      setSelected(articles[0]);
    }
  }, [articles, loading, selected]);

  const totalPages = Math.ceil(total / SIZE);
  const categoryItems = [
    { major_category: "", count: total },
    ...CATEGORY_FILTERS.map((category) => ({
      major_category: category,
      count: categories.find((c) => c.major_category === category)?.count ?? 0,
    })),
  ];
  const sourceItems = [
    { source: "", count: total },
    ...SOURCE_FILTERS.map((source) => ({
      source,
      count: sources.find((item) => item.source === source)?.count ?? 0,
    })),
  ];

  const handleCategoryClick = (cat) => {
    setSelectedCategory(cat);
    setPage(1);
    setSelected(null);
  };

  const handleSourceClick = (src) => {
    setSelectedSource(src);
    setPage(1);
    setSelected(null);
  };

  return (
    <div style={s.layout}>
      {/* Sidebar */}
      <aside style={s.sidebar}>
        <div style={s.sidebarHeader}>
          <div style={s.sidebarTitle}>📰 뉴스 뷰어</div>
          <div style={s.sidebarSubtitle}>크롤링 뉴스 모아보기</div>
        </div>
        <div style={s.sidebarScroll}>
          <div style={{ ...s.sectionLabel, marginTop: 4 }}>카테고리</div>
          {categoryItems.map((c) => (
            <div
              key={c.major_category}
              onClick={() => handleCategoryClick(c.major_category)}
              style={s.filterItem(selectedCategory === c.major_category)}
            >
              <span>{c.major_category || "전체"}</span>
              <span style={s.filterCount(selectedCategory === c.major_category)}>{c.count}</span>
            </div>
          ))}

          <div style={s.sectionLabel}>출처</div>
          {sourceItems.map((src) => (
            <div
              key={src.source}
              onClick={() => handleSourceClick(src.source)}
              style={s.filterItem(selectedSource === src.source)}
            >
              <span>{src.source || "전체"}</span>
              <span style={s.filterCount(selectedSource === src.source)}>{src.count}</span>
            </div>
          ))}
        </div>
      </aside>

      {/* Main */}
      <main style={s.main}>
        {/* Topbar */}
        <div style={s.topbar}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") { setSearch(query); setPage(1); setSelected(null); }
            }}
            placeholder="기사 제목, 내용으로 검색..."
            style={s.searchInput}
          />
          <button
            onClick={() => { setSearch(query); setPage(1); setSelected(null); }}
            style={s.searchBtn}
          >
            검색
          </button>
        </div>

        <div style={s.content}>
          {/* Article List */}
          <div style={s.listPanel}>
            {loading && <div style={s.statusText}>불러오는 중...</div>}
            {!loading && articles.length === 0 && (
              <div style={s.statusText}>기사가 없습니다</div>
            )}
            {!loading && articles.map((a) => (
              <div
                key={a.id}
                onClick={() => setSelected(a)}
                style={s.card(selected?.id === a.id)}
              >
                <div style={s.cardMeta}>
                  <span>{a.source}</span>
                  <span style={s.cardDot} />
                  <span>{a.major_category}</span>
                </div>
                <div style={s.cardTitle}>{a.title}</div>
                {a.summary && (
                  <div style={s.cardSummary}>
                    {a.summary.slice(0, 90)}…
                  </div>
                )}
                {(a.tags || []).length > 0 && (
                  <div style={s.tagRow}>
                    {(a.tags || []).slice(0, 3).map((t) => (
                      <span key={t} style={s.tag}>{t}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {totalPages > 1 && (
              <div style={s.pagination}>
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  style={s.pageBtn(page === 1)}
                >
                  이전
                </button>
                <span style={s.pageInfo}>{page} / {totalPages}</span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  style={s.pageBtn(page === totalPages)}
                >
                  다음
                </button>
              </div>
            )}
          </div>

          {/* Article Detail */}
          <div style={s.detailPanel}>
            {!selected ? (
              <div style={s.detailEmpty}>
                <span style={{ fontSize: 14 }}>기사를 선택하세요</span>
              </div>
            ) : (
              <>
                <div style={s.detailMeta}>
                  <span>{selected.source}</span>
                  <span>·</span>
                  <span>{selected.major_category}</span>
                  {selected.sub_category && (
                    <>
                      <span>·</span>
                      <span style={{ color: TEXT_SECONDARY }}>{selected.sub_category}</span>
                    </>
                  )}
                </div>
                <h1 style={s.detailTitle}>{selected.title}</h1>
                <div style={s.detailDate}>
                  <span>{selected.published_at?.slice(0, 10)}</span>
                  {selected.url && (
                    <>
                      <span>·</span>
                      <a href={selected.url} target="_blank" rel="noreferrer" style={s.detailLink}>
                        원문 보기 ↗
                      </a>
                    </>
                  )}
                </div>
                {selected.summary && (
                  <div style={s.summaryBox}>
                    <div style={s.summaryLabel}>AI 요약</div>
                    <div style={s.summaryText}>{selected.summary}</div>
                  </div>
                )}
                <div style={s.detailContent}>
                  {cleanArticleText(selected.content) || "이 기사는 원문 본문을 가져오지 못했습니다."}
                </div>
                {(selected.tags || []).length > 0 && (
                  <div style={s.tagRow}>
                    {(selected.tags || []).map((t) => (
                      <span key={t} style={{ ...s.tag, fontSize: 12, padding: "4px 12px" }}>{t}</span>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
