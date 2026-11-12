export const initialArticleState = {
  articles: [],
  total: 0,
  loading: true,
  error: "",
  selected: null,
  requestId: 0,
};

export function articleReducer(state, action) {
  switch (action.type) {
    case "START_FETCH":
      return {
        ...state,
        loading: true,
        selected: null,
        error: "",
        requestId: action.requestId ?? state.requestId + 1,
      };

    case "FETCH_SUCCESS": {
      // Discard stale responses from superseded requests
      if (action.requestId !== undefined && action.requestId !== state.requestId) {
        return state;
      }
      const articles = action.articles || [];
      let nextSelected = null;
      if (articles.length > 0) {
        if (state.selected && articles.some((a) => a.id === state.selected.id)) {
          nextSelected = state.selected;
        } else if (!action.isCompact) {
          nextSelected = articles[0];
        }
      }
      return {
        ...state,
        articles,
        total: action.total ?? 0,
        loading: false,
        error: "",
        selected: nextSelected,
      };
    }

    case "FETCH_ERROR": {
      // Discard stale error responses
      if (action.requestId !== undefined && action.requestId !== state.requestId) {
        return state;
      }
      return {
        ...state,
        articles: [],
        total: 0,
        loading: false,
        error: action.error || "기사를 불러오지 못했습니다. 서버 연결을 확인해 주세요.",
        selected: null,
      };
    }

    case "SELECT_ARTICLE": {
      const nextSelected =
        typeof action.payload === "function"
          ? action.payload(state.selected)
          : action.payload !== undefined
          ? action.payload
          : action.article;
      return {
        ...state,
        selected: nextSelected,
      };
    }

    case "RESIZE_VIEWPORT": {
      if (!action.isCompact) {
        // Transitioned to desktop: if no article is selected and not loading, auto-select first article
        if (!state.loading && state.articles.length > 0 && !state.selected) {
          return {
            ...state,
            selected: state.articles[0],
          };
        }
      }
      // If an article is already selected, retain it across both mobile and desktop transitions
      return state;
    }

    default:
      return state;
  }
}
