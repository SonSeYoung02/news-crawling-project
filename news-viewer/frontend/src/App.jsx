import { useEffect, useState, useRef, useReducer } from "react";
import { articleReducer, initialArticleState } from "./articleState.js";

const API = "/api";
const COMPACT_QUERY = "(max-width: 1023px)";

const ACCENT = "#7c3aed";
const ACCENT_LIGHT = "#ede9fe";
const ACCENT_MID = "#8b5cf6";
const BORDER = "#e5e7eb";
const TEXT_SECONDARY = "#6b7280";
const TEXT_MUTED = "#9ca3af";
const SOURCE_FILTERS = [
  "네이버뉴스",
  "Google News",
  "GeekNews",
  "Reddit AI",
  "GitHub Trending",
  "Hugging Face",
  "arXiv",
  "dev.to",
];

async function fetchJSON(path, signal) {
  const response = await fetch(`${API}${path}`, { signal });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

const cleanArticleText = (text = "") =>
  text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.includes("\uad11\uace0"))
    .join("\n");

const s = {
  layout: {
    display: "flex",
    height: "100dvh",
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
    minWidth: 0,
    minHeight: 0,
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
    minWidth: 0,
    padding: "9px 14px",
    borderRadius: 10,
    border: `1.5px solid ${BORDER}`,
    fontSize: 16,
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
    minHeight: 0,
    display: "flex",
    overflow: "hidden",
  },
  listPanel: {
    flex: "0 1 400px",
    minWidth: 280,
    overflowY: "auto",
    borderRight: `1px solid ${BORDER}`,
    background: "#f8fafc",
    padding: "12px 12px",
  },
  card: (selected) => ({
    width: "100%",
    textAlign: "left",
    fontFamily: "inherit",
    overflowWrap: "anywhere",
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
    minWidth: 0,
    overflowWrap: "anywhere",
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
  emptyState: {
    padding: "48px 16px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    textAlign: "center",
  },
  emptyIcon: {
    fontSize: 32,
    marginBottom: 12,
    opacity: 0.6,
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: 600,
    color: "#1f2937",
    marginBottom: 6,
    letterSpacing: "-0.2px",
  },
  emptyDesc: {
    fontSize: 13,
    color: "#4b5563",
    lineHeight: 1.5,
    maxWidth: 260,
    marginBottom: 18,
  },
  resetBtn: {
    padding: "8px 16px",
    borderRadius: 8,
    border: `1.5px solid ${BORDER}`,
    background: "#ffffff",
    color: ACCENT,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    transition: "background 0.15s, border-color 0.15s",
  },
  compactLayout: { flexDirection: "column" },
  compactSidebar: { width: "100%", flexShrink: 0, borderRight: "none", borderBottom: `1px solid ${BORDER}` },
  compactHeader: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "12px 16px", borderBottom: "none" },
  compactFilters: { maxHeight: "40dvh", padding: "0 12px 12px" },
  compactTopbar: { padding: "10px 12px", gap: 8 },
  compactList: { width: "100%", minWidth: 0, flex: 1, borderRight: "none" },
  compactDetail: { width: "100%", padding: "20px 16px", flex: 1 },
  filterButton: { minHeight: 44, padding: "8px 12px", border: `1px solid ${BORDER}`, borderRadius: 8, background: "#fff", color: ACCENT, font: "inherit", cursor: "pointer", flexShrink: 0 },
  filterControl: { width: "100%", minHeight: 44, border: "none", fontFamily: "inherit", textAlign: "left" },
  touchButton: { minHeight: 44 },
  backButton: { minHeight: 44, marginBottom: 16, padding: "8px 12px", border: `1px solid ${BORDER}`, borderRadius: 8, background: "#fff", color: ACCENT, font: "inherit", cursor: "pointer" },
  error: { padding: "12px 16px", color: "#991b1b", background: "#fef2f2", fontSize: 14, flexShrink: 0 },
};

export default function App() {
  const [categories, setCategories] = useState([]);
  const [sources, setSources] = useState([]);
  const [totalAll, setTotalAll] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedSource, setSelectedSource] = useState("");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [metadataError, setMetadataError] = useState("");
  const [isCompact, setIsCompact] = useState(() => window.matchMedia(COMPACT_QUERY).matches);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const [articleState, dispatch] = useReducer(articleReducer, initialArticleState);
  const { articles, total, loading, error, selected } = articleState;

  const setSelected = (articleOrUpdater) => {
    dispatch({ type: "SELECT_ARTICLE", payload: articleOrUpdater });
  };

  const reqIdRef = useRef(0);
  const activeReqRef = useRef(0);

  const isCompactRef = useRef(isCompact);
  useEffect(() => {
    isCompactRef.current = isCompact;
    dispatch({ type: "RESIZE_VIEWPORT", isCompact });
  }, [isCompact]);

  const SIZE = 20;

  useEffect(() => {
    const media = window.matchMedia(COMPACT_QUERY);
    const onChange = (event) => {
      setIsCompact(event.matches);
      setFiltersOpen(false);
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchJSON("/categories", controller.signal),
      fetchJSON("/sources", controller.signal),
      fetchJSON("/articles?page=1&size=1", controller.signal),
    ]).then(([categoryData, sourceData, articleData]) => {
      setCategories(categoryData);
      setSources(sourceData);
      setTotalAll(articleData.total);
    }).catch(() => {
      if (!controller.signal.aborted) setMetadataError("필터 정보를 불러오지 못했습니다. 서버 연결을 확인해 주세요.");
    });
    return () => controller.abort();
  }, []);

  const startFetch = () => {
    const nextReqId = ++reqIdRef.current;
    dispatch({ type: "START_FETCH", requestId: nextReqId });
    return nextReqId;
  };

  useEffect(() => {
    const controller = new AbortController();
    let currentReqId = reqIdRef.current;
    if (activeReqRef.current === currentReqId) {
      currentReqId = startFetch();
    }
    activeReqRef.current = currentReqId;

    const params = new URLSearchParams({ page, size: SIZE });
    if (selectedCategory) params.set("category", selectedCategory);
    if (selectedSource) params.set("source", selectedSource);
    if (search) params.set("q", search);

    fetchJSON(`/articles?${params}`, controller.signal)
      .then((data) => {
        dispatch({
          type: "FETCH_SUCCESS",
          requestId: currentReqId,
          articles: data.articles,
          total: data.total,
          isCompact: isCompactRef.current,
        });
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          dispatch({
            type: "FETCH_ERROR",
            requestId: currentReqId,
            error: "기사를 불러오지 못했습니다. 서버 연결을 확인해 주세요.",
          });
        }
      });

    return () => controller.abort();
  }, [page, selectedCategory, selectedSource, search]);

  const totalPages = Math.ceil(total / SIZE);
  const categoryItems = [
    { major_category: "", count: totalAll },
    ...categories,
  ];
  const sourceItems = [
    { source: "", count: totalAll },
    ...SOURCE_FILTERS.map((source) => ({
      source,
      count: sources.find((item) => item.source === source)?.count ?? 0,
    })),
  ];

  const handleCategoryClick = (cat) => {
    setFiltersOpen(false);
    startFetch();
    setSelectedCategory(cat);
    setSelectedSource("");
    setPage(1);
  };

  const handleSourceClick = (src) => {
    setFiltersOpen(false);
    startFetch();
    setSelectedSource(src);
    setSelectedCategory("");
    setPage(1);
  };

  const handleResetSearch = () => {
    startFetch();
    setQuery("");
    setSearch("");
    setPage(1);
  };

  const handleSearchSubmit = (e) => {
    e?.preventDefault();
    startFetch();
    setSearch(query);
    setPage(1);
  };

  const handlePageChange = (newPage) => {
    startFetch();
    setPage(newPage);
  };

  return (
    <div style={{ ...s.layout, ...(isCompact ? s.compactLayout : {}) }}>
      {/* Sidebar */}
      <aside style={{ ...s.sidebar, ...(isCompact ? s.compactSidebar : {}) }}>
        <div style={{ ...s.sidebarHeader, ...(isCompact ? s.compactHeader : {}) }}>
          <div>
            <div style={s.sidebarTitle}>📰 뉴스 뷰어</div>
            <div style={s.sidebarSubtitle}>크롤링 뉴스 모아보기</div>
          </div>
          {isCompact && (
            <button type="button" style={s.filterButton} aria-expanded={filtersOpen} aria-controls="news-filters" onClick={() => setFiltersOpen((open) => !open)}>
              {filtersOpen ? "필터 닫기" : "필터"}
            </button>
          )}
        </div>
        <div id="news-filters" hidden={isCompact && !filtersOpen} style={{ ...s.sidebarScroll, ...(isCompact ? s.compactFilters : {}) }}>
          <div style={{ ...s.sectionLabel, marginTop: 4 }}>카테고리</div>
          {categoryItems.map((c) => (
            <button
              type="button"
              key={c.major_category}
              aria-pressed={selectedCategory === c.major_category}
              onClick={() => handleCategoryClick(c.major_category)}
              style={{ ...s.filterItem(selectedCategory === c.major_category), ...s.filterControl }}
            >
              <span>{c.major_category || "전체"}</span>
              <span style={s.filterCount(selectedCategory === c.major_category)}>{c.count}</span>
            </button>
          ))}

          <div style={s.sectionLabel}>출처</div>
          {sourceItems.map((src) => (
            <button
              type="button"
              key={src.source}
              aria-pressed={selectedSource === src.source}
              onClick={() => handleSourceClick(src.source)}
              style={{ ...s.filterItem(selectedSource === src.source), ...s.filterControl }}
            >
              <span>{src.source || "전체"}</span>
              <span style={s.filterCount(selectedSource === src.source)}>{src.count}</span>
            </button>
          ))}
        </div>
      </aside>

      {/* Main */}
      <main style={s.main}>
        {/* Topbar */}
        <div style={{ ...s.topbar, ...(isCompact ? s.compactTopbar : {}) }}>
          <input
            aria-label="기사 검색"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearchSubmit(e);
            }}
            placeholder="기사 제목, 요약으로 검색..."
            style={s.searchInput}
          />
          <button
            onClick={handleSearchSubmit}
            style={{ ...s.searchBtn, ...s.touchButton }}
          >
            검색
          </button>
        </div>

        {(error || metadataError) && <div role="alert" style={s.error}>{error || metadataError}</div>}

        <div style={s.content}>
          {/* Article List */}
          <div aria-label="기사 목록" style={{ ...s.listPanel, ...(isCompact ? s.compactList : {}), ...(isCompact && selected ? { display: "none" } : {}) }}>
            {loading && <div style={s.statusText}>불러오는 중...</div>}
            {!loading && !error && articles.length === 0 && (
              search ? (
                <div style={s.emptyState}>
                  <div style={s.emptyIcon} aria-hidden="true">🔍</div>
                  <div style={s.emptyTitle}>
                    &lsquo;{search}&rsquo;에 대한 검색 결과가 없습니다
                  </div>
                  <div style={s.emptyDesc}>
                    단어의 철자가 정확한지 확인하거나 다른 검색어로 검색해 보세요.
                  </div>
                  <button
                    type="button"
                    onClick={handleResetSearch}
                    style={{ ...s.resetBtn, ...s.touchButton }}
                  >
                    검색어 초기화
                  </button>
                </div>
              ) : (
                <div style={s.statusText}>기사가 없습니다</div>
              )
            )}
            {!loading && articles.map((a) => (
              <button
                type="button"
                key={a.id}
                aria-pressed={selected?.id === a.id}
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
              </button>
            ))}

            {totalPages > 1 && (
              <div style={s.pagination}>
                <button
                  onClick={() => handlePageChange(Math.max(1, page - 1))}
                  disabled={page === 1}
                  style={{ ...s.pageBtn(page === 1), ...s.touchButton }}
                >
                  이전
                </button>
                <span style={s.pageInfo}>{page} / {totalPages}</span>
                <button
                  onClick={() => handlePageChange(Math.min(totalPages, page + 1))}
                  disabled={page === totalPages}
                  style={{ ...s.pageBtn(page === totalPages), ...s.touchButton }}
                >
                  다음
                </button>
              </div>
            )}
          </div>

          {/* Article Detail */}
          <div aria-label="기사 상세" style={{ ...s.detailPanel, ...(isCompact ? s.compactDetail : {}), ...(isCompact && !selected ? { display: "none" } : {}) }}>
            {!selected ? (
              <div style={s.detailEmpty}>
                <span style={{ fontSize: 14, color: TEXT_SECONDARY }}>
                  {loading
                    ? "기사를 불러오는 중..."
                    : error
                    ? "기사를 불러오지 못했습니다"
                    : articles.length === 0
                    ? (search ? "검색 결과가 없습니다" : "표시할 기사가 없습니다")
                    : "기사를 선택하세요"}
                </span>
              </div>
            ) : (
              <>
                {isCompact && <button type="button" style={s.backButton} onClick={() => setSelected(null)}>← 목록으로</button>}
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
                    <div style={s.summaryLabel}>LLM 분석</div>
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
