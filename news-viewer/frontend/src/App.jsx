import { useEffect, useState, useRef, useReducer } from "react";
import ArticleBody from "./ArticleBody";
import { articleReducer, initialArticleState } from "./articleState.js";

const API = "/api";
const COMPACT_QUERY = "(max-width: 1023px)";

const ACCENT = "#258347";
const ACCENT_LIGHT = "#edf5ef";
const ACCENT_MID = "#3d8b56";
const ACCENT_DARK = "#1e6837";
const BORDER = "#e4e8e4";
const TEXT_SECONDARY = "#4a574e";
const TEXT_MUTED = "#525e55";
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

const SOURCE_MARKS = {
  "네이버뉴스": ["N", "#1b874b", "#edf7ef"],
  "Google News": ["G", "#34629e", "#edf3fc"],
  GeekNews: ["GN", "#9e5c2c", "#fcf3ec"],
  "Reddit AI": ["R", "#b35732", "#fcf1ec"],
  "GitHub Trending": ["GH", "#36413a", "#edf1ee"],
  "Hugging Face": ["HF", "#8a6a20", "#fdf8e8"],
  arXiv: ["aX", "#9c4040", "#fdf0f0"],
  "dev.to": ["d", "#3f4c45", "#edf1ee"],
};

function SourceMark({ source, size = 18 }) {
  const [label, color, background] = SOURCE_MARKS[source] || [source?.slice(0, 2) || "뉴스", "#455348", "#edf1ee"];
  return (
    <span
      aria-hidden="true"
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: size,
        height: size,
        borderRadius: 4,
        fontSize: size <= 18 ? 9 : 10,
        lineHeight: 1,
        fontWeight: 700,
        color,
        background,
        flexShrink: 0,
        letterSpacing: "-0.3px",
      }}
    >
      {label}
    </span>
  );
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "short", day: "numeric" }).format(date);
}

async function fetchJSON(path, signal) {
  const response = await fetch(`${API}${path}`, { signal });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

const s = {
  layout: {
    display: "flex",
    height: "100dvh",
    overflow: "hidden",
    background: "#ffffff",
  },
  sidebar: {
    width: 240,
    background: "#f7f9f7",
    borderRight: `1px solid ${BORDER}`,
    display: "flex",
    flexDirection: "column",
    flexShrink: 0,
  },
  sidebarHeader: {
    padding: "20px 18px 16px",
    borderBottom: `1px solid ${BORDER}`,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  sidebarBrand: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  sidebarBrandIcon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    background: ACCENT,
    color: "#ffffff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: 750,
    fontSize: 16,
    flexShrink: 0,
  },
  sidebarTitle: {
    fontSize: 17,
    fontWeight: 750,
    color: "#16241a",
    letterSpacing: "-0.4px",
    lineHeight: 1.25,
  },
  sidebarSubtitle: {
    fontSize: 11,
    color: TEXT_MUTED,
    marginTop: 2,
    fontWeight: 500,
  },
  sidebarScroll: {
    flex: 1,
    minHeight: 0,
    overflowY: "auto",
    padding: "14px 10px 18px",
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: 700,
    color: TEXT_MUTED,
    textTransform: "uppercase",
    letterSpacing: "0.6px",
    padding: "0 10px",
    marginBottom: 6,
    marginTop: 18,
  },
  filterItem: (active) => ({
    width: "100%",
    minHeight: 44,
    padding: "8px 12px",
    borderRadius: 7,
    border: "none",
    cursor: "pointer",
    marginBottom: 2,
    background: active ? ACCENT_LIGHT : "transparent",
    color: active ? ACCENT_DARK : "#334136",
    fontWeight: active ? 650 : 450,
    fontSize: 13.5,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    transition: "background 0.15s, color 0.15s",
    fontFamily: "inherit",
    textAlign: "left",
  }),
  filterCount: (active) => ({
    fontSize: 11,
    color: active ? ACCENT_DARK : TEXT_MUTED,
    fontWeight: 500,
    fontVariantNumeric: "tabular-nums",
    background: active ? "#d7eadb" : "#edf2ee",
    padding: "2px 7px",
    borderRadius: 10,
  }),
  main: {
    flex: 1,
    minWidth: 0,
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    background: "#ffffff",
  },
  topbar: {
    minHeight: 64,
    padding: "12px 24px",
    borderBottom: `1px solid ${BORDER}`,
    background: "#ffffff",
    display: "flex",
    justifyContent: "space-between",
    gap: 16,
    alignItems: "center",
    flexShrink: 0,
  },
  topbarTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: "#334136",
    display: "flex",
    alignItems: "center",
    gap: 8,
    whiteSpace: "nowrap",
  },
  searchForm: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    flex: "0 1 380px",
    maxWidth: "100%",
  },
  searchInput: {
    flex: 1,
    minWidth: 0,
    padding: "9px 14px",
    borderRadius: 8,
    border: `1px solid ${BORDER}`,
    fontSize: 14,
    background: "#f8faf8",
    color: "#16241a",
    transition: "border-color 0.15s, background-color 0.15s",
    fontFamily: "inherit",
  },
  searchBtn: {
    padding: "9px 18px",
    borderRadius: 8,
    background: ACCENT,
    color: "#ffffff",
    border: "none",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 650,
    letterSpacing: "0.1px",
    flexShrink: 0,
    transition: "background 0.15s",
    fontFamily: "inherit",
  },
  content: {
    flex: 1,
    minHeight: 0,
    display: "flex",
    overflow: "hidden",
  },
  listPanel: {
    flex: "0 0 clamp(340px, 32vw, 480px)",
    minWidth: 320,
    overflowY: "auto",
    borderRight: `1px solid ${BORDER}`,
    background: "#ffffff",
    padding: 0,
  },
  activeFilterBar: {
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 8,
    padding: "10px 14px",
    margin: "12px 14px",
    background: "#f6f9f6",
    borderRadius: 8,
    border: "1px solid #dbe6dc",
    maxWidth: "calc(100% - 28px)",
    boxSizing: "border-box",
  },
  activeFilterLabel: {
    fontSize: 12,
    fontWeight: 650,
    color: "#28382c",
    marginRight: 2,
  },
  activeFilterChip: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    minHeight: 44,
    padding: "6px 12px",
    boxSizing: "border-box",
    borderRadius: 20,
    background: ACCENT_LIGHT,
    color: ACCENT_DARK,
    border: "1px solid #cce2d0",
    fontSize: 12.5,
    fontWeight: 550,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  activeFilterRemove: {
    fontSize: 11,
    fontWeight: 700,
    lineHeight: 1,
    color: "inherit",
  },
  filterResetBtn: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: 44,
    padding: "6px 10px",
    boxSizing: "border-box",
    borderRadius: 6,
    background: "transparent",
    color: TEXT_SECONDARY,
    border: "none",
    fontSize: 12,
    fontWeight: 500,
    cursor: "pointer",
    marginLeft: "auto",
    fontFamily: "inherit",
    textDecoration: "underline",
  },
  card: (selected) => ({
    width: "100%",
    textAlign: "left",
    fontFamily: "inherit",
    overflowWrap: "anywhere",
    padding: "16px 20px 15px",
    cursor: "pointer",
    background: selected ? "#edf5ef" : "#ffffff",
    border: "none",
    borderBottom: `1px solid ${BORDER}`,
    borderLeft: selected ? `3px solid ${ACCENT}` : "3px solid transparent",
    transition: "background 0.15s, border-left-color 0.15s",
    display: "block",
  }),
  cardMeta: {
    fontSize: 12,
    color: TEXT_MUTED,
    fontWeight: 500,
    marginBottom: 6,
    display: "flex",
    gap: 7,
    alignItems: "center",
    flexWrap: "wrap",
  },
  cardSourceName: {
    fontWeight: 650,
    color: "#2a3d2e",
  },
  cardCategory: {
    color: ACCENT_DARK,
    fontWeight: 550,
  },
  cardDate: {
    color: TEXT_MUTED,
  },
  cardDot: {
    width: 3,
    height: 3,
    borderRadius: "50%",
    background: "#98a69a",
    flexShrink: 0,
  },
  cardTitle: {
    fontSize: 14.5,
    fontWeight: 650,
    lineHeight: 1.45,
    marginBottom: 6,
    color: "#16241a",
  },
  cardSummary: {
    fontSize: 12.5,
    color: TEXT_SECONDARY,
    lineHeight: 1.55,
    marginBottom: 8,
  },
  tagRow: {
    display: "flex",
    gap: 5,
    flexWrap: "wrap",
  },
  tag: {
    fontSize: 11,
    background: "#edf5ef",
    color: ACCENT_DARK,
    border: "1px solid #d5e5d8",
    padding: "2px 8px",
    borderRadius: 14,
    fontWeight: 500,
  },
  pagination: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    gap: 12,
    padding: "16px 16px 20px",
    borderTop: `1px solid ${BORDER}`,
    background: "#ffffff",
  },
  pageBtn: (disabled) => ({
    padding: "6px 14px",
    borderRadius: 7,
    border: `1px solid ${BORDER}`,
    background: disabled ? "#f4f6f4" : "#ffffff",
    color: disabled ? TEXT_MUTED : "#28382c",
    cursor: disabled ? "default" : "pointer",
    fontSize: 12.5,
    fontWeight: 550,
    fontFamily: "inherit",
    transition: "background 0.15s, border-color 0.15s",
  }),
  pageInfo: {
    fontSize: 12.5,
    color: TEXT_MUTED,
    minWidth: 60,
    textAlign: "center",
    fontVariantNumeric: "tabular-nums",
  },
  readerContainer: {
    maxWidth: 780,
    width: "100%",
    margin: "0 auto",
    overflowWrap: "anywhere",
    wordBreak: "break-word",
  },
  detailPanel: {
    flex: 1,
    minWidth: 0,
    overflowY: "auto",
    padding: "36px 44px",
    background: "#ffffff",
  },
  detailEmpty: {
    height: "100%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: TEXT_MUTED,
    textAlign: "center",
    padding: "32px",
  },
  detailMeta: {
    display: "flex",
    gap: 8,
    alignItems: "center",
    fontSize: 13,
    color: ACCENT_DARK,
    fontWeight: 600,
    marginBottom: 12,
    flexWrap: "wrap",
  },
  detailTitle: {
    fontSize: 25,
    fontWeight: 750,
    lineHeight: 1.35,
    marginBottom: 14,
    color: "#142217",
    letterSpacing: "-0.02em",
    overflowWrap: "anywhere",
    wordBreak: "break-word",
  },
  detailDate: {
    fontSize: 12.5,
    color: TEXT_MUTED,
    marginBottom: 24,
    display: "flex",
    gap: 8,
    alignItems: "center",
  },
  detailLink: {
    color: ACCENT_DARK,
    textDecoration: "none",
    fontWeight: 550,
    display: "inline-flex",
    alignItems: "center",
    gap: 3,
  },
  summaryBox: {
    background: "#f4f8f4",
    border: "1px solid #d5e5d8",
    borderLeft: `4px solid ${ACCENT}`,
    borderRadius: 8,
    padding: "16px 20px",
    marginBottom: 28,
  },
  summaryLabel: {
    fontSize: 11,
    fontWeight: 700,
    color: ACCENT_DARK,
    textTransform: "uppercase",
    letterSpacing: "0.6px",
    marginBottom: 8,
  },
  summaryText: {
    fontSize: 14.5,
    lineHeight: 1.75,
    color: "#28382c",
  },
  detailContent: {
    fontSize: 17,
    lineHeight: 1.82,
    color: "#28382c",
    whiteSpace: "pre-wrap",
    marginBottom: 32,
    overflowWrap: "anywhere",
    wordBreak: "break-word",
  },
  statusText: {
    textAlign: "center",
    color: TEXT_MUTED,
    padding: "40px 16px",
    fontSize: 13.5,
  },
  briefingHeader: {
    padding: "24px 20px 20px",
    borderBottom: `1px solid ${BORDER}`,
    background: "#f4f8f4",
  },
  briefingTitle: {
    margin: "0 0 8px",
    fontSize: 19,
    fontWeight: 750,
    color: "#16241a",
    letterSpacing: "-0.3px",
  },
  briefingDescription: {
    margin: "0 0 8px",
    fontSize: 12.5,
    lineHeight: 1.6,
    color: TEXT_SECONDARY,
  },
  emptyState: {
    padding: "48px 20px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    textAlign: "center",
  },
  emptyIcon: {
    fontSize: 32,
    marginBottom: 12,
    opacity: 0.7,
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: 650,
    color: "#16241a",
    marginBottom: 6,
    letterSpacing: "-0.2px",
  },
  emptyDesc: {
    fontSize: 13,
    color: TEXT_SECONDARY,
    lineHeight: 1.5,
    maxWidth: 280,
    marginBottom: 18,
  },
  resetBtn: {
    padding: "8px 18px",
    borderRadius: 7,
    border: `1px solid ${BORDER}`,
    background: "#ffffff",
    color: ACCENT_DARK,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    transition: "background 0.15s, border-color 0.15s",
    fontFamily: "inherit",
  },
  compactLayout: { flexDirection: "column" },
  compactSidebar: { width: "100%", flexShrink: 0, borderRight: "none", borderBottom: `1px solid ${BORDER}` },
  compactHeader: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "12px 16px", borderBottom: "none" },
  compactFilters: { maxHeight: "40dvh", padding: "0 12px 14px" },
  compactTopbar: { padding: "10px 14px", gap: 8 },
  compactReadingHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "8px 14px",
    borderBottom: `1px solid ${BORDER}`,
    background: "#ffffff",
    minHeight: 52,
    gap: 12,
    flexShrink: 0,
  },
  compactReadingMeta: {
    fontSize: 13,
    color: TEXT_SECONDARY,
    fontWeight: 550,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  compactList: { width: "100%", minWidth: 0, flex: 1, borderRight: "none" },
  compactDetail: { width: "100%", padding: "20px 16px", flex: 1 },
  compactDetailTitle: { fontSize: 21, lineHeight: 1.35 },
  filterButton: {
    minHeight: 44,
    padding: "8px 14px",
    border: `1px solid ${BORDER}`,
    borderRadius: 7,
    background: "#ffffff",
    color: ACCENT_DARK,
    font: "inherit",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    flexShrink: 0,
  },
  filterControl: { width: "100%", minHeight: 44, border: "none", fontFamily: "inherit", textAlign: "left" },
  touchButton: { minHeight: 44 },
  backButton: {
    minHeight: 44,
    minWidth: 44,
    padding: "8px 14px",
    border: `1px solid ${BORDER}`,
    borderRadius: 7,
    background: "#ffffff",
    color: ACCENT_DARK,
    font: "inherit",
    fontSize: 13.5,
    fontWeight: 650,
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    flexShrink: 0,
  },
  error: { padding: "12px 16px", color: "#991b1b", background: "#fef2f2", fontSize: 13.5, flexShrink: 0, borderBottom: "1px solid #fee2e2" },
};

export default function App() {
  const [view, setView] = useState("briefing");
  const [briefing, setBriefing] = useState(null);
  const [briefingLoading, setBriefingLoading] = useState(true);
  const [briefingError, setBriefingError] = useState("");
  const [briefingRetry, setBriefingRetry] = useState(0);

  const [categories, setCategories] = useState([]);
  const [sources, setSources] = useState([]);
  const [totalAll, setTotalAll] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedSource, setSelectedSource] = useState("");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [fetchRev, setFetchRev] = useState(0);
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

  const viewRef = useRef(view);
  useEffect(() => {
    viewRef.current = view;
  }, [view]);

  const isCompactRef = useRef(isCompact);
  useEffect(() => {
    isCompactRef.current = isCompact;
    dispatch({ type: "RESIZE_VIEWPORT", isCompact, view });
  }, [isCompact, view]);

  const listRef = useRef(null);
  const listScrollPos = useRef(0);

  const handleSelectArticle = (article) => {
    if (listRef.current) {
      listScrollPos.current = listRef.current.scrollTop;
    }
    setSelected(article);
  };

  const handleBackToList = () => {
    setSelected(null);
  };

  useEffect(() => {
    if (!selected && isCompact && listRef.current && listScrollPos.current > 0) {
      requestAnimationFrame(() => {
        if (listRef.current) {
          listRef.current.scrollTop = listScrollPos.current;
        }
      });
    }
  }, [selected, isCompact]);

  const SIZE = 20;

  useEffect(() => {
    if (view !== "briefing") return;
    const controller = new AbortController();
    setSelected(null);
    setBriefingLoading(true);
    setBriefingError("");
    fetchJSON("/briefing", controller.signal)
      .then((data) => {
        setBriefing(data);
        if (!isCompactRef.current && (data?.articles || []).length > 0) {
          setSelected(data.articles[0]);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setBriefingError("브리핑을 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setBriefingLoading(false);
      });
    return () => controller.abort();
  }, [view, briefingRetry]);

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
    ])
      .then(([categoryData, sourceData, articleData]) => {
        setCategories(categoryData);
        setSources(sourceData);
        setTotalAll(articleData.total);
      })
      .catch(() => {
        if (!controller.signal.aborted) setMetadataError("필터 정보를 불러오지 못했습니다. 서버 연결을 확인해 주세요.");
      });
    return () => controller.abort();
  }, []);

  const startFetch = () => {
    const nextReqId = ++reqIdRef.current;
    dispatch({ type: "START_FETCH", requestId: nextReqId, view: viewRef.current });
    return nextReqId;
  };

  const triggerFetch = () => {
    startFetch();
    setFetchRev((r) => r + 1);
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
          view: viewRef.current,
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
  }, [page, selectedCategory, selectedSource, search, fetchRev]);

  useEffect(() => {
    if (view === "briefing" && !isCompact && !briefingLoading && !selected && (briefing?.articles || []).length > 0) {
      setSelected(briefing.articles[0]);
    }
  }, [view, isCompact, briefingLoading, selected, briefing]);

  useEffect(() => {
    if (view === "articles" && !isCompact && !loading && !selected && articles.length > 0) {
      setSelected(articles[0]);
    }
  }, [view, isCompact, loading, selected, articles]);

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
    setView("articles");
    setFiltersOpen(false);
    triggerFetch();
    setSelectedCategory((prev) => (prev === cat ? "" : cat));
    setPage(1);
    listScrollPos.current = 0;
    if (listRef.current) listRef.current.scrollTop = 0;
  };

  const handleSourceClick = (src) => {
    setView("articles");
    setFiltersOpen(false);
    triggerFetch();
    setSelectedSource((prev) => (prev === src ? "" : src));
    setPage(1);
    listScrollPos.current = 0;
    if (listRef.current) listRef.current.scrollTop = 0;
  };

  const handleResetFilters = () => {
    setView("articles");
    triggerFetch();
    setSelectedCategory("");
    setSelectedSource("");
    setPage(1);
    listScrollPos.current = 0;
    if (listRef.current) listRef.current.scrollTop = 0;
  };

  const handleResetSearch = () => {
    setView("articles");
    triggerFetch();
    setQuery("");
    setSearch("");
    setPage(1);
    listScrollPos.current = 0;
    if (listRef.current) listRef.current.scrollTop = 0;
  };

  const handleSearchSubmit = (e) => {
    e?.preventDefault();
    setView("articles");
    triggerFetch();
    setSearch(query);
    setPage(1);
    listScrollPos.current = 0;
    if (listRef.current) listRef.current.scrollTop = 0;
  };

  const handlePageChange = (newPage) => {
    triggerFetch();
    setPage(newPage);
    listScrollPos.current = 0;
    if (listRef.current) listRef.current.scrollTop = 0;
  };

  return (
    <div style={{ ...s.layout, ...(isCompact ? s.compactLayout : {}) }}>
      {/* Sidebar */}
      <aside style={{ ...s.sidebar, ...(isCompact ? s.compactSidebar : {}) }}>
        <div style={{ ...s.sidebarHeader, ...(isCompact ? s.compactHeader : {}) }}>
          <div style={s.sidebarBrand}>
            <div style={s.sidebarBrandIcon}>📰</div>
            <div>
              <div style={s.sidebarTitle}>뉴스 뷰어</div>
              <div style={s.sidebarSubtitle}>크롤링 뉴스 모아보기</div>
            </div>
          </div>
          {isCompact && (
            <button
              type="button"
              style={s.filterButton}
              aria-expanded={filtersOpen}
              aria-controls="news-filters"
              onClick={() => setFiltersOpen((open) => !open)}
            >
              {filtersOpen ? "필터 닫기" : "필터"}
            </button>
          )}
        </div>
        <div id="news-filters" hidden={isCompact && !filtersOpen} style={{ ...s.sidebarScroll, ...(isCompact ? s.compactFilters : {}) }}>
          <div style={s.sectionLabel}>보기</div>
          {[
            { id: "briefing", label: "오늘의 AI 브리핑" },
            { id: "articles", label: "전체 기사" },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={view === item.id}
              style={{ ...s.filterItem(view === item.id), ...s.filterControl }}
              onClick={() => {
                if (view !== item.id) {
                  setView(item.id);
                  setSelected(null);
                }
                setFiltersOpen(false);
              }}
            >
              {item.label}
            </button>
          ))}

          <div style={{ ...s.sectionLabel, marginTop: 12 }}>카테고리</div>
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
        {/* Compact Reading Header */}
        {isCompact && selected && (
          <header style={s.compactReadingHeader}>
            <button
              type="button"
              style={s.backButton}
              onClick={handleBackToList}
              aria-label="기사 목록으로 돌아가기"
            >
              ← 목록
            </button>
            <span style={s.compactReadingMeta}>
              {selected.source} · {selected.major_category}
            </span>
          </header>
        )}

        {/* Topbar */}
        <div style={{ ...s.topbar, ...(isCompact ? s.compactTopbar : {}), ...(isCompact && selected ? { display: "none" } : {}) }}>
          {!isCompact && (
            <div style={s.topbarTitle}>
              <span>{view === "briefing" ? "오늘의 AI 브리핑" : "기사 피드"}</span>
              {view === "articles" && (selectedCategory || selectedSource) && (
                <span style={{ fontSize: 12, color: TEXT_MUTED, fontWeight: 400 }}>
                  {selectedCategory && `· ${selectedCategory}`}
                  {selectedSource && `· ${selectedSource}`}
                </span>
              )}
            </div>
          )}
          <form onSubmit={handleSearchSubmit} style={s.searchForm}>
            <input
              aria-label="기사 검색"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSearchSubmit(e);
              }}
              placeholder="기사 제목, 본문으로 검색..."
              style={s.searchInput}
            />
            <button
              type="submit"
              onClick={handleSearchSubmit}
              style={{ ...s.searchBtn, ...s.touchButton }}
            >
              검색
            </button>
          </form>
        </div>

        {((view === "articles" && error) || metadataError) && (
          <div role="alert" style={s.error}>
            {(view === "articles" && error) || metadataError}
          </div>
        )}

        <div style={s.content}>
          {/* Article List / Briefing List */}
          <div
            ref={listRef}
            aria-label={view === "briefing" ? "오늘의 AI 브리핑 목록" : "기사 목록"}
            style={{
              ...s.listPanel,
              ...(isCompact ? s.compactList : {}),
              ...(isCompact && selected ? { display: "none" } : {}),
            }}
          >
            {view === "briefing" && (
              <section aria-label="오늘의 AI 브리핑" style={s.briefingHeader}>
                <h2 style={s.briefingTitle}>오늘의 AI 브리핑</h2>
                <p style={s.briefingDescription}>최근 24시간의 AI 소식 최대 5개를 모았습니다.</p>
                <p style={s.briefingDescription}>주제·출처 다양성과 최신순을 반영한 선정입니다.</p>
                {briefing && (
                  <p style={s.briefingDescription}>
                    조회 시각: {new Date(briefing.generated_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} (한국 시간)
                  </p>
                )}
                <button
                  type="button"
                  style={s.filterButton}
                  disabled={briefingLoading}
                  onClick={() => setBriefingRetry((n) => n + 1)}
                >
                  새로고침
                </button>
              </section>
            )}

            {view === "briefing" && briefingLoading && (
              <div role="status" style={s.statusText}>브리핑을 불러오는 중...</div>
            )}
            {view === "briefing" && briefingError && (
              <div role="alert" style={s.error}>
                {briefingError}{" "}
                <button type="button" style={s.filterButton} onClick={() => setBriefingRetry((n) => n + 1)}>
                  다시 시도
                </button>
              </div>
            )}
            {view === "briefing" && !briefingLoading && !briefingError && (briefing?.articles || []).length === 0 && (
              <div style={s.statusText}>최근 24시간에 수집된 AI 기사가 없습니다.</div>
            )}

            {view === "articles" && (selectedCategory || selectedSource) && (
              <div style={s.activeFilterBar} aria-label="활성 필터">
                <span style={s.activeFilterLabel}>적용된 필터:</span>
                {selectedCategory && (
                  <button
                    type="button"
                    style={s.activeFilterChip}
                    onClick={() => handleCategoryClick("")}
                    aria-label={`카테고리: ${selectedCategory} 필터 해제`}
                  >
                    <span>카테고리: {selectedCategory}</span>
                    <span style={s.activeFilterRemove} aria-hidden="true">✕</span>
                  </button>
                )}
                {selectedSource && (
                  <button
                    type="button"
                    style={s.activeFilterChip}
                    onClick={() => handleSourceClick("")}
                    aria-label={`출처: ${selectedSource} 필터 해제`}
                  >
                    <span>출처: {selectedSource}</span>
                    <span style={s.activeFilterRemove} aria-hidden="true">✕</span>
                  </button>
                )}
                <button
                  type="button"
                  style={s.filterResetBtn}
                  onClick={handleResetFilters}
                >
                  필터 초기화
                </button>
              </div>
            )}

            {view === "articles" && loading && <div style={s.statusText}>불러오는 중...</div>}
            {view === "articles" && !loading && !error && articles.length === 0 && (
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

            {(view === "briefing"
              ? (!briefingLoading && !briefingError ? briefing?.articles || [] : [])
              : (!loading ? articles : [])
            ).map((a) => {
              const previewText = a.summary || a.content;
              return (
                <button
                  type="button"
                  key={a.id}
                  aria-pressed={selected?.id === a.id}
                  onClick={() => handleSelectArticle(a)}
                  style={s.card(selected?.id === a.id)}
                >
                  <div style={s.cardMeta}>
                    <SourceMark source={a.source} />
                    <span style={s.cardSourceName}>{a.source}</span>
                    <span style={s.cardDot} />
                    <span style={s.cardCategory}>{a.major_category}</span>
                    {a.published_at && (
                      <>
                        <span style={s.cardDot} />
                        <span style={s.cardDate}>{formatDate(a.published_at)}</span>
                      </>
                    )}
                  </div>
                  <div style={s.cardTitle}>{a.title}</div>
                  {previewText && (
                    <div style={s.cardSummary}>
                      {previewText.slice(0, 95)}{previewText.length > 95 ? "…" : ""}
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
              );
            })}

            {view === "articles" && totalPages > 1 && (
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
          <div
            aria-label="기사 상세"
            style={{
              ...s.detailPanel,
              ...(isCompact ? s.compactDetail : {}),
              ...(isCompact && !selected ? { display: "none" } : {}),
            }}
          >
            {!selected ? (
              <div style={s.detailEmpty}>
                <span style={{ fontSize: 14, color: TEXT_SECONDARY }}>
                  {view === "briefing"
                    ? (briefingLoading
                        ? "브리핑을 불러오는 중..."
                        : briefingError
                        ? "브리핑을 불러오지 못했습니다"
                        : (briefing?.articles || []).length === 0
                        ? "최근 24시간에 수집된 AI 기사가 없습니다"
                        : "기사를 선택하세요")
                    : (loading
                        ? "기사를 불러오는 중..."
                        : error
                        ? "기사를 불러오지 못했습니다"
                        : articles.length === 0
                        ? (search ? "검색 결과가 없습니다" : "표시할 기사가 없습니다")
                        : "기사를 선택하세요")}
                </span>
              </div>
            ) : (
              <div style={s.readerContainer}>
                <div style={s.detailMeta}>
                  <SourceMark source={selected.source} size={20} />
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
                <h1 style={{ ...s.detailTitle, ...(isCompact ? s.compactDetailTitle : {}) }}>{selected.title}</h1>
                <div style={s.detailDate}>
                  <span>{formatDate(selected.published_at) || selected.published_at?.slice(0, 10)}</span>
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
                <ArticleBody content={selected.content} style={s.detailContent} />
                {(selected.tags || []).length > 0 && (
                  <div style={s.tagRow}>
                    {(selected.tags || []).map((t) => (
                      <span key={t} style={{ ...s.tag, fontSize: 12, padding: "4px 12px" }}>{t}</span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
