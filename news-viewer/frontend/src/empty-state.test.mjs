import test from "node:test";
import assert from "node:assert/strict";
import { articleReducer, initialArticleState } from "./articleState.js";

test("Issue #34 Regression: SUBMIT_SEARCH immediately sets loading=true and selected=null (prevents stale article in loading transition)", () => {
  // Simulate active desktop state with an article open
  const previousState = {
    ...initialArticleState,
    loading: false,
    articles: [
      { id: 1, title: "기사 1 (Plan Stamping)" },
      { id: 2, title: "기사 2" },
    ],
    selected: { id: 1, title: "기사 1 (Plan Stamping)" },
    query: "없는검색어12345",
    search: "",
    requestId: 1,
  };

  const nextState = articleReducer(previousState, { type: "SUBMIT_SEARCH" });

  assert.equal(nextState.loading, true, "Loading must be immediately true during search submission");
  assert.equal(nextState.selected, null, "Selected article must be immediately null to avoid stale detail flash");
  assert.equal(nextState.search, "없는검색어12345");
  assert.equal(nextState.page, 1);
  assert.equal(nextState.requestId, 2, "RequestId must increment to invalidate pending responses");
});

test("Issue #34 Regression: FETCH_SUCCESS with 0 results strictly enforces selected=null", () => {
  const loadingState = {
    ...initialArticleState,
    loading: true,
    articles: [{ id: 1, title: "이전 기사" }],
    selected: null,
    search: "없는검색어12345",
    requestId: 3,
  };

  const nextState = articleReducer(loadingState, {
    type: "FETCH_SUCCESS",
    requestId: 3,
    articles: [],
    total: 0,
    isCompact: false, // Desktop
  });

  assert.equal(nextState.loading, false);
  assert.equal(nextState.articles.length, 0);
  assert.equal(nextState.total, 0);
  assert.equal(nextState.selected, null, "Selection must be null when results are 0");
});

test("Issue #34 Regression: Fast request switching rejects late stale responses", () => {
  // Initial state where request 5 is current (e.g. search for "없는검색어")
  const currentState = {
    ...initialArticleState,
    loading: true,
    articles: [],
    total: 0,
    selected: null,
    search: "없는검색어",
    requestId: 5,
  };

  // Stale Request 4 (e.g. earlier search for "AI") finishes late with 20 articles
  const staleResponse = {
    type: "FETCH_SUCCESS",
    requestId: 4, // Older requestId!
    articles: [{ id: 99, title: "구 요청 기사 (AI)" }],
    total: 100,
    isCompact: false,
  };

  const afterStaleResponse = articleReducer(currentState, staleResponse);

  // Must not accept stale response!
  assert.equal(afterStaleResponse.articles.length, 0, "Stale articles must be discarded");
  assert.equal(afterStaleResponse.selected, null, "Stale article must not be selected");
  assert.equal(afterStaleResponse.loading, true, "Loading state for current request must remain true");
  assert.equal(afterStaleResponse.requestId, 5);

  // Now current Request 5 arrives with 0 results
  const currentResponse = {
    type: "FETCH_SUCCESS",
    requestId: 5,
    articles: [],
    total: 0,
    isCompact: false,
  };

  const finalState = articleReducer(afterStaleResponse, currentResponse);
  assert.equal(finalState.loading, false);
  assert.equal(finalState.articles.length, 0);
  assert.equal(finalState.selected, null);
});

test("Issue #34 Regression: RESET_SEARCH preserves selectedCategory and selectedSource", () => {
  const filteredState = {
    ...initialArticleState,
    selectedCategory: "AI",
    selectedSource: "GeekNews",
    query: "없는검색어",
    search: "없는검색어",
    page: 2,
    selected: null,
    requestId: 7,
  };

  const resetState = articleReducer(filteredState, { type: "RESET_SEARCH" });

  assert.equal(resetState.query, "", "Query must be cleared");
  assert.equal(resetState.search, "", "Search must be cleared");
  assert.equal(resetState.page, 1, "Page must be reset to 1");
  assert.equal(resetState.selected, null);
  assert.equal(resetState.selectedCategory, "AI", "selectedCategory must be preserved");
  assert.equal(resetState.selectedSource, "GeekNews", "selectedSource must be preserved");
  assert.equal(resetState.requestId, 8, "RequestId must increment for refetch");
});

test("Issue #34 Regression: RESIZE_VIEWPORT bidirectional preservation and loading guard", () => {
  const article3 = { id: 3, title: "기사 3번" };
  const article1 = { id: 1, title: "기사 1번" };

  // Scenario 1: Mobile -> Desktop retains active selection (does NOT force article1)
  const mobileWithSelection = {
    ...initialArticleState,
    articles: [article1, article3],
    selected: article3,
    loading: false,
  };
  const toDesktop = articleReducer(mobileWithSelection, {
    type: "RESIZE_VIEWPORT",
    isCompact: false,
  });
  assert.equal(toDesktop.selected.id, 3, "Mobile to Desktop must retain existing selection");

  // Scenario 2: Desktop -> Mobile retains active selection (does NOT set null)
  const toMobile = articleReducer(toDesktop, {
    type: "RESIZE_VIEWPORT",
    isCompact: true,
  });
  assert.equal(toMobile.selected.id, 3, "Desktop to Mobile must retain existing selection");

  // Scenario 3: Mobile with NO selection -> Desktop auto-selects first article
  const mobileNoSelection = {
    ...initialArticleState,
    articles: [article1, article3],
    selected: null,
    loading: false,
  };
  const toDesktopAutoSelect = articleReducer(mobileNoSelection, {
    type: "RESIZE_VIEWPORT",
    isCompact: false,
  });
  assert.equal(toDesktopAutoSelect.selected.id, 1, "Desktop auto-selects first article when none was selected");

  // Scenario 4: Mobile -> Desktop while loading does NOT select stale articles
  const mobileLoading = {
    ...initialArticleState,
    articles: [article1, article3],
    selected: null,
    loading: true, // Fetch currently in progress
  };
  const toDesktopWhileLoading = articleReducer(mobileLoading, {
    type: "RESIZE_VIEWPORT",
    isCompact: false,
  });
  assert.equal(toDesktopWhileLoading.selected, null, "Must NOT auto-select stale articles while loading");
});

test("Issue #34 Regression: Dynamic screen mode on fetch completion respects current viewport", () => {
  const loadingState = {
    ...initialArticleState,
    loading: true,
    requestId: 10,
  };

  // Case A: Response arrives when user is currently on mobile
  const mobileArrival = articleReducer(loadingState, {
    type: "FETCH_SUCCESS",
    requestId: 10,
    articles: [{ id: 1, title: "기사 1" }],
    total: 1,
    isCompact: true,
  });
  assert.equal(mobileArrival.selected, null, "Mobile arrival must keep selection null for explicit tap");

  // Case B: Response arrives when user is currently on desktop
  const desktopArrival = articleReducer(loadingState, {
    type: "FETCH_SUCCESS",
    requestId: 10,
    articles: [{ id: 1, title: "기사 1" }],
    total: 1,
    isCompact: false,
  });
  assert.equal(desktopArrival.selected.id, 1, "Desktop arrival must auto-select first article");
});
