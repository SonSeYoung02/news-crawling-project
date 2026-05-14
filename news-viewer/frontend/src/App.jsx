import { useEffect, useState } from "react";

const API = "http://localhost:8000";

function App() {
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

  const totalPages = Math.ceil(total / SIZE);

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "sans-serif" }}>
      {/* 사이드바 */}
      <aside style={{ width: 220, background: "#1e1e2e", color: "#cdd6f4", padding: 20, overflowY: "auto", flexShrink: 0 }}>
        <h2 style={{ margin: "0 0 20px", fontSize: 18 }}>뉴스 뷰어</h2>

        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 12, color: "#a6adc8", marginBottom: 8 }}>카테고리</div>
          {[{ major_category: "", count: total }, ...categories].map((c) => (
            <div
              key={c.major_category}
              onClick={() => { setSelectedCategory(c.major_category); setPage(1); }}
              style={{
                padding: "6px 10px", borderRadius: 6, cursor: "pointer", marginBottom: 4,
                background: selectedCategory === c.major_category ? "#313244" : "transparent",
                fontSize: 14,
              }}
            >
              {c.major_category || "전체"} <span style={{ color: "#a6adc8", fontSize: 12 }}>({c.count})</span>
            </div>
          ))}
        </div>

        <div>
          <div style={{ fontSize: 12, color: "#a6adc8", marginBottom: 8 }}>출처</div>
          {[{ source: "", count: total }, ...sources].map((s) => (
            <div
              key={s.source}
              onClick={() => { setSelectedSource(s.source); setPage(1); }}
              style={{
                padding: "6px 10px", borderRadius: 6, cursor: "pointer", marginBottom: 4,
                background: selectedSource === s.source ? "#313244" : "transparent",
                fontSize: 14,
              }}
            >
              {s.source || "전체"} <span style={{ color: "#a6adc8", fontSize: 12 }}>({s.count})</span>
            </div>
          ))}
        </div>
      </aside>

      {/* 메인 */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* 검색바 */}
        <div style={{ padding: "16px 24px", borderBottom: "1px solid #e5e7eb", display: "flex", gap: 8 }}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { setSearch(query); setPage(1); } }}
            placeholder="기사 검색..."
            style={{ flex: 1, padding: "8px 14px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 14 }}
          />
          <button
            onClick={() => { setSearch(query); setPage(1); }}
            style={{ padding: "8px 18px", borderRadius: 8, background: "#6c63ff", color: "#fff", border: "none", cursor: "pointer", fontSize: 14 }}
          >
            검색
          </button>
        </div>

        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          {/* 기사 목록 */}
          <div style={{ width: 420, overflowY: "auto", borderRight: "1px solid #e5e7eb", padding: 16 }}>
            {loading && <div style={{ textAlign: "center", color: "#9ca3af", padding: 40 }}>로딩 중...</div>}
            {!loading && articles.length === 0 && (
              <div style={{ textAlign: "center", color: "#9ca3af", padding: 40 }}>기사가 없습니다</div>
            )}
            {articles.map((a) => (
              <div
                key={a.id}
                onClick={() => setSelected(a)}
                style={{
                  padding: 14, borderRadius: 10, marginBottom: 10, cursor: "pointer",
                  background: selected?.id === a.id ? "#ede9fe" : "#f9fafb",
                  border: selected?.id === a.id ? "1px solid #6c63ff" : "1px solid #e5e7eb",
                }}
              >
                <div style={{ fontSize: 13, color: "#6c63ff", marginBottom: 4 }}>
                  {a.source} · {a.major_category}
                </div>
                <div style={{ fontSize: 15, fontWeight: 600, lineHeight: 1.4, marginBottom: 6 }}>{a.title}</div>
                {a.summary && (
                  <div style={{ fontSize: 13, color: "#6b7280", lineHeight: 1.5 }}>
                    {a.summary.slice(0, 100)}...
                  </div>
                )}
                <div style={{ marginTop: 8, display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {(a.tags || []).slice(0, 3).map((t) => (
                    <span key={t} style={{ fontSize: 11, background: "#e0e7ff", color: "#4338ca", padding: "2px 8px", borderRadius: 20 }}>{t}</span>
                  ))}
                </div>
              </div>
            ))}

            {/* 페이지네이션 */}
            {totalPages > 1 && (
              <div style={{ display: "flex", justifyContent: "center", gap: 8, padding: "16px 0" }}>
                <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                  style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid #d1d5db", cursor: "pointer" }}>이전</button>
                <span style={{ padding: "6px 0", fontSize: 14, color: "#6b7280" }}>{page} / {totalPages}</span>
                <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                  style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid #d1d5db", cursor: "pointer" }}>다음</button>
              </div>
            )}
          </div>

          {/* 기사 상세 */}
          <div style={{ flex: 1, overflowY: "auto", padding: 32 }}>
            {!selected ? (
              <div style={{ textAlign: "center", color: "#9ca3af", marginTop: 80 }}>기사를 선택하세요</div>
            ) : (
              <>
                <div style={{ fontSize: 13, color: "#6c63ff", marginBottom: 8 }}>
                  {selected.source} · {selected.major_category} · {selected.sub_category}
                </div>
                <h1 style={{ fontSize: 22, fontWeight: 700, lineHeight: 1.4, marginBottom: 16 }}>{selected.title}</h1>
                <div style={{ fontSize: 13, color: "#9ca3af", marginBottom: 20 }}>
                  {selected.published_at?.slice(0, 10)} · <a href={selected.url} target="_blank" rel="noreferrer" style={{ color: "#6c63ff" }}>원문 보기</a>
                </div>
                {selected.summary && (
                  <div style={{ background: "#f5f3ff", border: "1px solid #ede9fe", borderRadius: 10, padding: 16, marginBottom: 20 }}>
                    <div style={{ fontSize: 12, color: "#7c3aed", fontWeight: 600, marginBottom: 8 }}>AI 요약</div>
                    <div style={{ fontSize: 14, lineHeight: 1.7, color: "#374151" }}>{selected.summary}</div>
                  </div>
                )}
                <div style={{ fontSize: 15, lineHeight: 1.8, color: "#374151", whiteSpace: "pre-wrap" }}>{selected.content}</div>
                <div style={{ marginTop: 20, display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {(selected.tags || []).map((t) => (
                    <span key={t} style={{ fontSize: 12, background: "#e0e7ff", color: "#4338ca", padding: "4px 12px", borderRadius: 20 }}>{t}</span>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
