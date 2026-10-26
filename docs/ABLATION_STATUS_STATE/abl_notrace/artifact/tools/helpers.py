"""Generic helpers available in the AppWorld REPL before step 1.

All helpers are app-agnostic: the caller passes `apis` plus the app name and API name as strings.
Soft rule: use them when they save you work; if one does not fit the task, write plain code instead.
"""
import re
import json
import math
import datetime
import itertools
import collections
import functools


PAGING_ARGS = "page_index page_limit"


TOKEN_ARGS = "access_token"


def _call_adaptive(fn, kwargs):
    """Call fn(**kwargs). Public detail APIs take no access_token. If the call fails because an access token
    argument is unexpected, retry ONCE without it and print a note. Any other unexpected/unknown argument (a
    filter such as a minimum or a genre) is NEVER dropped silently: the error is raised with a hint, because a
    dropped filter would silently return too many items."""
    try:
        return fn(**kwargs)
    except Exception as exc:
        msg = str(exc)
        low = msg.lower()
        if any(w in low for w in ("unexpected", "unknown", "not allowed", "extra", "unrecognized", "not permitted")):
            drop = [k for k in kwargs if k in TOKEN_ARGS.split() and k in msg]
            if drop:
                print("note: this API takes no %s (public API); retried without it" % ", ".join(drop))
                return fn(**{k: v for k, v in kwargs.items() if k not in drop})
            named = [k for k in kwargs if k not in PAGING_ARGS.split() and k in msg]
            if named:
                raise ValueError("%s  [HINT: %s is not a parameter of this API. It was NOT dropped. Read the exact "
                                 "parameter names in show_api_doc; if the API has no such filter, apply the "
                                 "condition in Python on the full result.]" % (msg[:300], ", ".join(named)))
        raise


def fetch_all_pages(apis, app_name, api_name, page_limit=20, max_pages=200, **kwargs):
    """Call a paginated list API over ALL pages and return one combined list.
    Example: items = fetch_all_pages(apis, app_name, api_name, access_token=token, query="x")
    Pass the API's own filter arguments as keyword arguments. Stops at the first empty page."""
    fn = getattr(getattr(apis, app_name), api_name)
    limits = [page_limit] + [x for x in (20, 10, 5) if x < page_limit]
    out = []
    prev_sig = None
    limit_idx = 0
    page_index = 0
    while page_index < max_pages:
        try:
            page = _call_adaptive(fn, dict(kwargs, page_index=page_index, page_limit=limits[limit_idx]))
        except Exception as exc:
            if page_index == 0 and "page_limit" in str(exc) and limit_idx + 1 < len(limits):
                limit_idx += 1
                continue
            raise
        if not isinstance(page, list):
            if page_index == 0:
                return page
            break
        if not page:
            break
        sig = json.dumps(page, sort_keys=True, default=str)
        if sig == prev_sig:
            break
        prev_sig = sig
        out.extend(page)
        page_index += 1
    return out


def call_each(apis, app_name, api_name, id_param, ids, **kwargs):
    """Call one API once per id - for reads (details) AND writes (like/follow/delete/download...).
    Returns (results, errors): dicts keyed by id. Duplicate ids are called once.
    Example: details, errs = call_each(apis, app_name, api_name, "song_id", song_ids, access_token=token)
    Pass access_token only if that API's doc lists it (public detail APIs take none); if the API rejects an
    extra argument by name, the call is retried once without it.
    A failure never stops the loop: ALWAYS print `errors` afterwards and fix or explain each one."""
    fn = getattr(getattr(apis, app_name), api_name)
    results, errors = {}, {}
    for one_id in ids:
        if one_id in results or one_id in errors:
            continue
        try:
            results[one_id] = _call_adaptive(fn, dict(kwargs, **{id_param: one_id}))
        except Exception as exc:
            errors[one_id] = str(exc)[:200]
    if errors:
        first = next(iter(errors))
        print("call_each(%s): %d of %d calls FAILED (ok=%d). First error for id %r: %s"
              % (api_name, len(errors), len(errors) + len(results), len(results), first, errors[first]))
    return results, errors


def try_call(apis, app_name, api_name, **kwargs):
    """Call an API without raising. Returns (True, result) or (False, error_message).
    Use it to test existence (e.g. 'does this person have an account?') or to skip items that fail."""
    try:
        return True, _call_adaptive(getattr(getattr(apis, app_name), api_name), kwargs)
    except Exception as exc:
        return False, str(exc)[:300]


def peek(obj, n=2, width=400):
    """Print a SHORT view of a result: type, length, keys and the first n items (cut to `width` chars).
    Use it instead of printing big lists, so the output does not flood your context."""
    if isinstance(obj, (list, tuple)):
        print("list of", len(obj), "items; first", min(n, len(obj)), ":")
        for item in obj[:n]:
            text = json.dumps(item, default=str)
            print(" ", text[:width] + ("..." if len(text) > width else ""))
        if obj and isinstance(obj[0], dict):
            print("  keys:", sorted(obj[0].keys()))
    elif isinstance(obj, dict):
        print("dict keys:", sorted(obj.keys()))
        text = json.dumps(obj, default=str)
        print(" ", text[: width * 2] + ("..." if len(text) > width * 2 else ""))
    else:
        text = repr(obj)
        print(text[: width * 2])


def unique_by(items, key):
    """Drop duplicates, keeping the first occurrence. `key` is a field name or a function."""
    getter = key if callable(key) else (lambda x: x[key])
    seen, out = set(), []
    for item in items:
        k = getter(item)
        if k in seen:
            continue
        seen.add(k)
        out.append(item)
    return out


def collect_ids(items, list_key):
    """Union (order kept, no duplicates) of the id lists found under `list_key` in each item.
    Example: all_song_ids = collect_ids(playlists, list_key) where each playlist holds a list of ids."""
    seen, out = set(), []
    for item in items:
        for one in (item.get(list_key) or []):
            if one not in seen:
                seen.add(one)
                out.append(one)
    return out


def top_n(items, key, n=1, largest=True):
    """Rank items by a numeric field (or function). Returns (chosen, ties).
    `ties` = other items whose value equals the value of the last chosen item. If ties is not empty the
    cut-off is ambiguous: print them and decide using any other criterion the task gives."""
    getter = key if callable(key) else (lambda x: x[key])
    ordered = sorted(items, key=getter, reverse=largest)
    chosen = ordered[:n]
    ties = []
    if chosen and len(ordered) > n:
        edge = getter(chosen[-1])
        ties = [x for x in ordered[n:] if getter(x) == edge]
    return chosen, ties


def norm_text(value):
    """Lower-case, trim and collapse whitespace; for comparing names/titles/emails."""
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def date_range(today, kind, n=1):
    """Inclusive (start_date, end_date) as 'YYYY-MM-DD' strings relative to `today` ('YYYY-MM-DD...' string).
    kind: 'today', 'yesterday', 'this_month', 'last_month', 'this_year', 'last_year',
          'last_n_days' (n days ending today, today included).
    Example: start, end = date_range(today, 'yesterday')"""
    d = datetime.date.fromisoformat(str(today)[:10])
    one = datetime.timedelta(days=1)
    if kind == "today":
        s = e = d
    elif kind == "yesterday":
        s = e = d - one
    elif kind == "this_month":
        s, e = d.replace(day=1), d
        nxt = (s.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        e = nxt - one
    elif kind == "last_month":
        e = d.replace(day=1) - one
        s = e.replace(day=1)
    elif kind == "this_year":
        s, e = datetime.date(d.year, 1, 1), datetime.date(d.year, 12, 31)
    elif kind == "last_year":
        s, e = datetime.date(d.year - 1, 1, 1), datetime.date(d.year - 1, 12, 31)
    elif kind == "last_n_days":
        s, e = d - datetime.timedelta(days=int(n) - 1), d
    else:
        raise ValueError("unknown kind %r; use today/yesterday/this_month/last_month/this_year/last_year/last_n_days" % (kind,))
    return s.isoformat(), e.isoformat()


def in_dates(timestamp, start, end):
    """True if the DATE part of a timestamp string ('YYYY-MM-DD...') lies in [start, end] (both 'YYYY-MM-DD')."""
    return str(start)[:10] <= str(timestamp)[:10] <= str(end)[:10]


def days_since(timestamp, today):
    """Whole days between a timestamp string and `today` (both 'YYYY-MM-DD...'); positive if timestamp is earlier."""
    a = datetime.date.fromisoformat(str(timestamp)[:10])
    b = datetime.date.fromisoformat(str(today)[:10])
    return (b - a).days


def shift_clock(time_str, minutes):
    """Shift a clock time 'HH:MM' (or 'HH:MM:SS') by +/- minutes, wrapping past midnight. Keeps the input format."""
    parts = str(time_str).split(":")
    total = int(parts[0]) * 60 + int(parts[1]) + int(minutes)
    total %= 24 * 60
    out = "%02d:%02d" % (total // 60, total % 60)
    if len(parts) > 2:
        out += ":" + parts[2]
    return out


_DATE_TIME_RE = (r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b|\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b|"
                 r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?")
_NUM = r"\d[\d,]*(?:\.\d+)?"


def _to_float(txt):
    try:
        return float(txt.replace(",", ""))
    except ValueError:
        return None


def extract_amounts(text):
    """Money amounts found in a text, as floats, in order of appearance. Dates and clock times are ignored.
    If the text contains currency-marked amounts ('$12.50', '12 dollars', 'USD 12') ONLY those are returned;
    otherwise every plain number is returned. A text may hold several amounts (subtotal, tax, total): use
    amounts_with_context(text) to see which label belongs to which number before choosing one."""
    t = re.sub(_DATE_TIME_RE, " ", str(text), flags=re.I)
    marked = re.findall(r"\$\s*(" + _NUM + r")|\b(" + _NUM + r")\s*(?:dollars?|usd|bucks)\b|\busd\s*(" + _NUM + r")", t, flags=re.I)
    vals = [_to_float(next(g for g in m if g)) for m in marked]
    if not vals:
        vals = [_to_float(x) for x in re.findall(_NUM, t)]
    return [v for v in vals if v is not None]


def amounts_with_context(text, width=35):
    """List of (amount, 'text around it') for every money-like number in a text (dates/times skipped), so you can
    tell a total from a subtotal, a share or a fee. Print it, then pick the number the task is about."""
    t = re.sub(_DATE_TIME_RE, lambda m: " " * len(m.group(0)), str(text), flags=re.I)
    out = []
    for m in re.finditer(r"\$?\s*(" + _NUM + r")", t):
        v = _to_float(m.group(1))
        if v is None:
            continue
        lo, hi = max(0, m.start() - width), min(len(t), m.end() + width)
        out.append((v, " ".join(str(text)[lo:hi].split())))
    return out


def equal_share(total, people):
    """Equal share of `total` among `people` (count), rounded to 2 decimals.
    Remember to count yourself when the task says 'shared equally among my X and me'."""
    return round(float(total) / int(people), 2)


def make_csv(header, rows, sep=","):
    """Build CSV text: `header` is a list of column names, `rows` a list of lists. Cells containing the
    separator, a double quote or a newline are quoted. Lines are joined with newline, no trailing newline.
    To store several values in one cell (e.g. artists) join them first: "|".join(names)."""
    def cell(v):
        t = "" if v is None else str(v)
        if sep in t or '"' in t or "\n" in t:
            t = '"' + t.replace('"', '""') + '"'
        return t
    return "\n".join(sep.join(cell(c) for c in r) for r in [list(header)] + [list(r) for r in rows])


def require_fields(items, fields):
    """Guard before filtering/ranking on fields. Raises ValueError naming how many records lack each field
    (missing or None), so a silent `.get(field, '')` cannot make a filter match nothing. Returns items.
    If it raises, list items are only summaries: fetch the detail API for every id (call_each), then merge."""
    fields = [fields] if isinstance(fields, str) else list(fields)
    bad = {}
    for f in fields:
        n = sum(1 for it in items if not isinstance(it, dict) or it.get(f) is None)
        if n:
            bad[f] = n
    if bad:
        raise ValueError("records are missing fields %s (counts of %d records). The list API returns summaries: "
                         "call the detail API for every id with call_each and read these fields from there."
                         % (bad, len(items)))
    return items


def merge_details(items, details, id_key):
    """Return copies of `items` (list of dicts) with the matching detail dict merged in (detail wins on
    shared keys). `details` is the results dict from call_each, keyed by id; `id_key` is the id field
    of each item. Items without a detail are kept unchanged."""
    out = []
    for it in items:
        d = details.get(it.get(id_key))
        merged = dict(it)
        if isinstance(d, dict):
            merged.update(d)
        out.append(merged)
    return out


def contacts_with_relation(contacts, words):
    """Contacts whose `relationships` list matches ANY of `words` (case/punctuation-insensitive, singular or
    plural: 'sibling' ~ 'Siblings', 'co-worker' ~ 'coworker'). Example: people = contacts_with_relation(all_contacts, ['roommate', 'coworker'])
    ALWAYS print the distinct relationship strings first and pass every string that fits the task wording."""
    def key(x):
        k = re.sub(r"[^a-z]", "", str(x).lower())
        return k[:-1] if k.endswith("s") else k
    want = {key(w) for w in words}
    return [c for c in contacts if any(key(r) in want for r in (c.get("relationships") or []))]


def still_needed(targets, existing):
    """Targets not yet in `existing` (order kept). Use it so a write is never repeated:
    to_do = still_needed(target_ids, already_done_ids)."""
    have = set(existing)
    return [t for t in targets if t not in have]


def year_of(timestamp):
    """Year (int) of a 'YYYY-MM-DD...' string such as a release_date. 'before 2021' means year_of(x) < 2021."""
    return int(str(timestamp)[:4])


def with_prefix(path, prefix):
    """Add `prefix` to the file NAME of a path, keeping its directory: with_prefix('~/a/b.txt', '2023-01-02_')
    -> '~/a/2023-01-02_b.txt'. Use it to build rename targets for move_file."""
    head, sep, tail = str(path).rpartition("/")
    return head + sep + str(prefix) + tail


def swap_dir(path, new_dir):
    """Same file name in another directory: swap_dir('~/a/b.txt', '~/trash/') -> '~/trash/b.txt'."""
    return str(new_dir).rstrip("/") + "/" + str(path).rpartition("/")[2]


def check_targets(targets, universe=None, label="targets"):
    """Sanity check for a computed target list BEFORE a bulk write or a final answer. Prints the size and warns
    when the list is empty, has duplicates, or equals the WHOLE universe (a sign that your filter did nothing -
    e.g. an argument the API ignored). Returns the de-duplicated list (order kept).
    Example: ids = check_targets(ids, universe=all_ids, label="songs to like")
    It only prints warnings; if the whole set really is the right answer for the task, go ahead."""
    seen, out = set(), []
    for t in targets:
        k = json.dumps(t, sort_keys=True, default=str)
        if k not in seen:
            seen.add(k)
            out.append(t)
    msg = "%s: %d item(s)" % (label, len(out))
    if len(out) != len(list(targets)):
        msg += " (removed %d duplicate(s))" % (len(list(targets)) - len(out))
    print(msg)
    if not out:
        print("WARNING: %s is EMPTY - re-check the filter, the date range, the field names and that every page was read." % label)
    elif universe is not None:
        uni = {json.dumps(u, sort_keys=True, default=str) for u in universe}
        if len(uni) > 1 and uni <= seen:
            print("WARNING: %s equals the ENTIRE collection (%d items) - the filter probably did nothing. "
                  "Apply the task's condition in Python before writing." % (label, len(uni)))
    return out


def round_half_up(value, digits=0):
    """Round the way people do (2.5 -> 3, 0.125 -> 0.13), unlike Python's round() which rounds halves to even.
    Use it when a task says 'rounded to the nearest ...'. Returns an int when digits == 0, else a float."""
    q = 10 ** int(digits)
    r = math.floor(float(value) * q + 0.5 + 1e-9) / q
    return int(r) if int(digits) == 0 else r
