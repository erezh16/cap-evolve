"""Helper functions defined in the AppWorld REPL before step 1 (capability: tools)."""


def fetch_all(apis, app, api, page_limit=20, max_pages=100, **kwargs):
    """Return the full list from a paginated list/search API by looping page_index with page_limit=20 until an empty or repeated page. Example: fetch_all(apis, app_name, api_name, access_token=tok, query='x')."""
    fn = getattr(getattr(apis, app), api)
    out, prev = [], None
    for p in range(max_pages):
        try:
            page = fn(page_index=p, page_limit=page_limit, **kwargs)
        except Exception as e:
            if p == 0 and 'Unexpected parameter' in str(e):
                return fn(**kwargs)
            raise
        if not isinstance(page, list):
            return page if p == 0 else out
        if not page or page == prev:
            break
        out.extend(page)
        prev = page
    return out
