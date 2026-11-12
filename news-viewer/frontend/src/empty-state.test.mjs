import test from "node:test";
import assert from "node:assert/strict";
import { articleReducer, initialArticleState } from "./articleState.js";

test("Issue #34 Regression: START_FETCH synchronously sets loading=true and selected=null (prevents stale article in loading transition)", () => {
  // Simulate active desktop state with an article open
  const previousState = {
    ...initialArticleState,
    loading: false,
    articles: [
      { id: 1, title: "기사 1 (Plan Stamping)" },
      { id: 2, title: "기사 2" },
    ],
    selected: { id: 1, title: "기사 1 (Plan Stamping)" },
    error: "이전 에러",
    requestId: 1,
  };

  const nextState = articleReducer(previousState, { type: "START_FETCH", requestId: 2 });

  assert.equal(nextState.loading, true, "Loading must be immediately true during request start");
  assert.equal(nextState.selected, null, "Selected article must be immediately null to avoid stale detail flash");
  assert.equal(nextState.error, "", "Error must be cleared on start");
  assert.equal(nextState.requestId, 2, "RequestId must update to new request sequence");
});

test("Issue #34 Regression: FETCH_SUCCESS with 0 results strictly enforces selected=null", () => {
  const loadingState = {
    ...initialArticleState,
    loading: true,
    articles: [{ id: 1, title: "이전 기사" }],
    selected: null,
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
  // Current state waiting for Request 5
  const currentState = {
    ...initialArticleState,
    loading: true,
    articles: [],
    total: 0,
    selected: null,
    requestId: 5,
  };

  // Stale Request 4 finishes late with 20 articles
  const staleResponse = {
    type: "FETCH_SUCCESS",
    requestId: 4, // Older requestId
    articles: [{ id: 99, title: "구 요청 기사" }],
    total: 100,
    isCompact: false,
  };

  const afterStaleResponse = articleReducer(currentState, staleResponse);

  // Must not accept stale response
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

test("Issue #34 Regression: FETCH_ERROR cleans state and rejects stale error", () => {
  const loadingState = {
    ...initialArticleState,
    loading: true,
    articles: [{ id: 1, title: "이전 기사" }],
    selected: null,
    requestId: 7,
  };

  // Stale error for Request 6
  const staleError = articleReducer(loadingState, {
    type: "FETCH_ERROR",
    requestId: 6,
    error: "오래된 에러",
  });
  assert.equal(staleError.error, "");
  assert.equal(staleError.loading, true);

  // Current error for Request 7
  const currentError = articleReducer(loadingState, {
    type: "FETCH_ERROR",
    requestId: 7,
    error: "서버 에러",
  });
  assert.equal(currentError.loading, false);
  assert.equal(currentError.articles.length, 0);
  assert.equal(currentError.selected, null);
  assert.equal(currentError.error, "서버 에러");
});

test("Issue #34 Regression: SELECT_ARTICLE supports both object and functional updater (setSelected contract)", () => {
  const articleA = { id: 10, title: "기사 A" };
  const articleB = { id: 20, title: "기사 B" };

  const state1 = articleReducer(initialArticleState, {
    type: "SELECT_ARTICLE",
    payload: articleA,
  });
  assert.equal(state1.selected?.id, 10);

  // Functional updater
  const state2 = articleReducer(state1, {
    type: "SELECT_ARTICLE",
    payload: (prev) => (prev?.id === 10 ? articleB : null),
  });
  assert.equal(state2.selected?.id, 20);

  // Null selection (e.g. mobile back button)
  const state3 = articleReducer(state2, {
    type: "SELECT_ARTICLE",
    payload: null,
  });
  assert.equal(state3.selected, null);
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
