export const initialArticleState = {
  articles: [],
  total: 0,
  loading: true,
  error: "",
  selected: null,
  page: 1,
  query: "",
  search: "",
  selectedCategory: "",
  selectedSource: "",
  requestId: 0,
};

export function articleReducer(state, action) {
  switch (action.type) {
    case "SET_QUERY":
      return {
        ...state,
        query: action.query,
      };

    case "SUBMIT_SEARCH":
      return {
        ...state,
        search: state.query,
        page: 1,
        selected: null,
        loading: true,
        error: "",
        requestId: state.requestId + 1,
      };

    case "RESET_SEARCH":
      return {
        ...state,
        query: "",
        search: "",
        page: 1,
        selected: null,
        loading: true,
        error: "",
        requestId: state.requestId + 1,
        // selectedCategory and selectedSource are preserved
      };

    case "SET_CATEGORY":
      return {
        ...state,
        selectedCategory: action.category,
        selectedSource: "",
        page: 1,
        selected: null,
        loading: true,
        error: "",
        requestId: state.requestId + 1,
      };

    case "SET_SOURCE":
      return {
        ...state,
        selectedSource: action.source,
        selectedCategory: "",
        page: 1,
        selected: null,
        loading: true,
        error: "",
        requestId: state.requestId + 1,
      };

    case "SET_PAGE":
      return {
        ...state,
        page: action.page,
        selected: null,
        loading: true,
        error: "",
        requestId: state.requestId + 1,
      };

    case "FETCH_SUCCESS": {
      // Discard stale responses from superseded requests
      if (action.requestId !== state.requestId) {
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
      if (action.requestId !== state.requestId) {
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

    case "SELECT_ARTICLE":
      return {
        ...state,
        selected: action.article,
      };

    case "CLEAR_SELECTION":
      return {
        ...state,
        selected: null,
      };

    case "RESIZE_VIEWPORT": {
      // action.isCompact is the new viewport mode
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
