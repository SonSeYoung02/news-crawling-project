import test from "node:test";
import assert from "node:assert/strict";

test("Issue #34: search reset action preserves category and source filters", () => {
  const initialState = {
    selectedCategory: "AI",
    selectedSource: "GeekNews",
    query: "없는검색어",
    search: "없는검색어",
    page: 3,
    selected: { id: 10, title: "이전 기사" },
  };

  // Simulating handleResetSearch
  const resetSearch = (state) => ({
    ...state,
    query: "",
    search: "",
    page: 1,
    selected: null,
  });

  const nextState = resetSearch(initialState);

  assert.equal(nextState.query, "");
  assert.equal(nextState.search, "");
  assert.equal(nextState.page, 1);
  assert.equal(nextState.selected, null);
  assert.equal(nextState.selectedCategory, "AI", "selectedCategory must be preserved");
  assert.equal(nextState.selectedSource, "GeekNews", "selectedSource must be preserved");
});

test("Issue #34: request sequencing discards stale responses from older requests", () => {
  let latestRequestId = 0;
  let currentState = {
    articles: [{ id: 1, title: "기사 1" }],
    total: 1,
    selected: { id: 1, title: "기사 1" },
    loading: false,
  };

  // Request 1 fired
  const req1 = ++latestRequestId;
  currentState.loading = true;
  currentState.selected = null;

  // Rapidly, Request 2 fired before Request 1 resolves
  const req2 = ++latestRequestId;

  // Request 2 resolves first with 0 results
  const res2 = { articles: [], total: 0 };
  if (req2 === latestRequestId) {
    currentState.articles = res2.articles;
    currentState.total = res2.total;
    currentState.selected = null;
    currentState.loading = false;
  }

  assert.equal(currentState.articles.length, 0);
  assert.equal(currentState.selected, null);

  // Request 1 resolves late with old results
  const res1 = { articles: [{ id: 1, title: "기사 1" }], total: 1 };
  if (req1 === latestRequestId) {
    currentState.articles = res1.articles;
    currentState.total = res1.total;
    currentState.selected = res1.articles[0];
  }

  // Verify Request 1 was rejected and did NOT resurrect stale selection
  assert.equal(currentState.articles.length, 0, "Stale articles must not overwrite new empty result");
  assert.equal(currentState.selected, null, "Stale selection must not be resurrected");
});

test("Issue #34: empty search results enforce null selection", () => {
  const isCompact = false;
  const articles = [];
  const selected = { id: 99, title: "이전 기사" };

  // Helper matching the selection agreement logic
  const resolveSelection = (articles, currentSelected, isCompact) => {
    if (articles.length === 0) return null;
    if (!isCompact && (!currentSelected || !articles.some((a) => a.id === currentSelected.id))) {
      return articles[0];
    }
    return currentSelected;
  };

  const nextSelected = resolveSelection(articles, selected, isCompact);
  assert.equal(nextSelected, null, "Selection must be null when articles array is empty");
});
