"""Helpers available in the REPL."""


def paginate(api_func, **kwargs):
    """Call a paginated list API (pass the function itself, e.g. apis.<app>.<api>, plus its keyword args,
    including access_token if the API needs one) over all pages (page_limit=20) and return the flat list."""
    items = []
    page_index = 0
    while True:
        page = api_func(page_index=page_index, page_limit=20, **kwargs)
        if not page:
            break
        items.extend(page)
        page_index += 1
        if page_index > 200:
            break
    return items

