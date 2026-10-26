"""Generic REPL helpers (take `apis`, an API callable, or plain data). Return types:
  get_password(passwords, name) -> str;  login_app(apis, app, login_api, username, password) -> token str
  fetch_all(api_callable, **kw) -> LIST over all pages (do not pass page_index/page_limit; max_pages=None ok)
  safe_call(api_callable, **kw) -> (ok, result_or_error_text);  fetch_details(callable, ids, id_param) -> LIST
  collect_ids(items, *keys) -> ids (no key = auto-detect *_id, warns if none);  uniq_by/sort_by/count_by/top_with_ties
  as_date(x) -> date;  iso(x) -> 'YYYY-MM-DD';  shift_days/month_start -> ISO text;  parse_long_date;  clock_date
  day_range(x) -> (start, end);  in_range(ts, start, end);  ym(ts);  name_ym(path);  path_parts(p);  same_path(a, b)
  sum_labeled/labeled_amount(text, label);  amounts_in(text);  to_csv(rows, columns);  names_of(items, key, sep)
  req_state(req);  has_exact_email(rows, email);  contacts_by_relationship;  usable_cards(cards, date);  norm; digits; show
"""
import re
import json
import datetime

def get_password(passwords, account_name):
    """Return the password of `account_name` from the list returned by the supervisor passwords API."""
    for entry in passwords:
        if entry.get("account_name") == account_name:
            return entry.get("password")
    names = [e.get("account_name") for e in passwords]
    raise KeyError("no account named %r; available: %s" % (account_name, names))

def _token(text):
    """Token text that also answers tok['access_token'] / tok.get('access_token') with itself."""

    class Token(str):
        def __getitem__(self, i):
            return str(self) if i == "access_token" else str.__getitem__(self, i)

        def get(self, key, default=None):
            return str(self) if key == "access_token" else default

    return Token(text)

def login_app(apis, app_name, login_api, username, password):
    """Call apis.<app_name>.<login_api>(username=..., password=...) and return the access token STRING."""
    fn = getattr(getattr(apis, app_name), login_api)
    result = fn(username=username, password=password)
    if isinstance(result, dict) and "access_token" in result:
        return _token(result["access_token"])
    raise RuntimeError("login failed: %s" % (result,))

def _outcome(ok, value):
    """Tuple (ok, value) that, if used like the bare result (res.get(..), res['key']), forwards to the value
    when ok and raises the API's error text when not ok."""

    class Outcome(tuple):
        def _res(self, what):
            if tuple.__getitem__(self, 0):
                return tuple.__getitem__(self, 1)
            raise RuntimeError("API call failed (%s): %s" % (what, tuple.__getitem__(self, 1)))

        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            return getattr(self._res(name), name)

        def __getitem__(self, i):
            if isinstance(i, (int, slice)):
                return tuple.__getitem__(self, i)
            return self._res(repr(i))[i]

    return Outcome((ok, value))

def safe_call(api_callable, **kwargs):
    """Call an API; ALWAYS returns the tuple (ok, result): (True, result) or (False, error text). Never raises.
    Write `ok, res = safe_call(fn, ...)`. Retries once without access_token if the API is public."""
    try:
        return _outcome(True, api_callable(**kwargs))
    except Exception as exc:
        if "access_token" in kwargs and "Unexpected parameter 'access_token'" in str(exc):
            return safe_call(api_callable, **{k: v for k, v in kwargs.items() if k != "access_token"})
        return _outcome(False, "%s: %s" % (type(exc).__name__, exc))

def fetch_all(api_callable, limit=20, max_pages=200, **kwargs):
    """LIST of every item of a paginated listing API. Pass the callable plus its normal keyword args; page_index /
    page_limit in kwargs are ignored (handled here). Pages of `limit` (max 20) are requested until a page is
    empty or shorter than `limit`. limit=None is treated as 20 (APIs without paging params fall back to one call).
    max_pages=None means 'no cap'. Always returns a list (a dict response holding exactly one list value yields
    that list)."""
    kwargs.pop("page_index", None)
    kwargs.pop("page_limit", None)
    limit = 20 if limit is None else max(1, min(int(limit), 20))
    max_pages = 500 if max_pages is None else int(max_pages)
    items, first_prev = [], None
    for page in range(max_pages):
        try:
            res = api_callable(page_index=page, page_limit=limit, **kwargs)
        except Exception as exc:
            if page == 0 and "Unexpected parameter" in str(exc):
                return _as_list(api_callable(**kwargs))
            raise
        part = _as_list(res)
        if page > 0 and part and part[0] == first_prev:
            break
        first_prev = part[0] if part else first_prev
        items.extend(part)
        if len(part) < limit:
            break
    return items

def _as_list(res):
    if isinstance(res, list):
        return list(res)
    if res is None:
        return []
    if isinstance(res, dict):
        lists = [v for v in res.values() if isinstance(v, list)]
        if len(lists) == 1:
            return list(lists[0])
    return [res]

def collect_ids(items, *keys, **opts):
    """Ordered unique ids from listing items (dicts, or bare ids). With NO key it auto-detects the id field
    (song_id / album_id / playlist_id / artist_id / id / any single '*_id' field); pass keys or key='song_id'
    to be explicit. A list value contributes all its entries, a list of dicts their 'id'. Prints a warning when
    items is not empty but no id was found (never silently returns [])."""
    keys = list(keys)
    if opts.get("key"):
        keys.append(opts["key"])
    items = _as_list(items) if not isinstance(items, (list, tuple)) else list(items)
    seen = []

    def add(v):
        if isinstance(v, dict):
            v = v.get("id", v.get("song_id", v.get("album_id", v.get("playlist_id", v.get("artist_id")))))
        if v is not None and v not in seen:
            seen.append(v)

    for item in items:
        if not isinstance(item, dict):
            if item is not None and not isinstance(item, (list, tuple)):
                add(item)
            continue
        use = keys
        if not use:
            id_keys = ("song_id", "album_id", "playlist_id", "artist_id", "user_id", "id", "song_ids", "album_ids")
            use = [k for k in id_keys if k in item][:1]
            if not use:
                use = [k for k in item if str(k).endswith("_id") or str(k).endswith("_ids")][:1]
        for key in use:
            val = item.get(key)
            if val is None:
                continue
            for v in (val if isinstance(val, list) else [val]):
                add(v)
    if items and not seen:
        sample = items[0]
        print("collect_ids WARNING: no ids found in %d item(s); item keys: %s" % (
            len(items), sorted(sample) if isinstance(sample, dict) else type(sample).__name__))
    return seen

def fetch_details(detail_callable, ids, id_param, **kwargs):
    """Call detail_callable(<id_param>=id, **kwargs) for each id. Returns a LIST of the detail dicts, in id order
    (failed ids are skipped; their error texts are in fetch_details.errors, {id: text}). Never a tuple."""
    ids = list(ids)
    if not ids:
        print("fetch_details WARNING: no ids given, nothing fetched")
    out, errors = [], {}
    for i in ids:
        ok, res = safe_call(detail_callable, **dict(kwargs, **{id_param: i}))
        if ok:
            out.append(res)
        else:
            errors[i] = res
    fetch_details.errors = errors
    if errors:
        print("fetch_details: %d of %d calls failed, e.g. %s" % (len(errors), len(ids), list(errors.items())[0]))
    return out

def uniq_by(items, key):
    """Drop duplicate items by the value of item[key] (or key(item) if callable), keeping the first occurrence."""
    f = key if callable(key) else (lambda x: x.get(key))
    seen, out = set(), []
    for item in items:
        k = f(item)
        if k in seen:
            continue
        seen.add(k)
        out.append(item)
    return out

def sort_by(items, key, reverse=False):
    """Sort by item[key] (or key(item)); None values go last."""
    f = key if callable(key) else (lambda x: x.get(key))
    have = [x for x in items if f(x) is not None]
    miss = [x for x in items if f(x) is None]
    return sorted(have, key=f, reverse=reverse) + miss

def top_with_ties(items, key, n=1, largest=True):
    """Items whose value is among the n best distinct values (ties all kept; may exceed n). key: field or fn."""
    f = key if callable(key) else (lambda x: x.get(key))
    vals = sorted({f(x) for x in items if f(x) is not None}, reverse=largest)[:n]
    return [x for x in items if f(x) in vals]

def count_by(values):
    """Return {value: count} for an iterable of hashable values, most frequent first."""
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

def norm(text):
    """Lowercase, trim and collapse whitespace."""
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()

def digits(text):
    """Only the digits of a string, as ONE str (compare phone numbers with this)."""
    return re.sub(r"\D", "", str(text or ""))

def parse_dt(text):
    """Parse a date-like value ('YYYY-MM-DD', ISO timestamp with optional fraction/Z, date/datetime objects) to
    datetime. Regex based, so it also works with frozen/fake date classes."""
    if hasattr(text, "year") and hasattr(text, "hour"):
        return datetime.datetime(text.year, text.month, text.day, text.hour, text.minute, text.second)
    if hasattr(text, "year") and hasattr(text, "month") and hasattr(text, "day"):
        return datetime.datetime(text.year, text.month, text.day)
    s = str(text).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?", s)
    if not m:
        raise ValueError("unrecognised date text: %r" % (text,))
    y, mo, d, hh, mi, ss = [int(g) if g else 0 for g in m.groups()]
    return datetime.datetime(y, mo, d, hh, mi, ss)

def parse_long_date(text):
    """Parse text like 'Thursday, May 18, 2023' (the phone clock API's date) to a datetime.date."""
    months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
              "november", "december"]
    m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", str(text))
    if m:
        for i, name in enumerate(months):
            if name.startswith(m.group(1).lower()) and len(m.group(1)) >= 3:
                return datetime.date(int(m.group(3)), i + 1, int(m.group(2)))
    raise ValueError("unrecognised long date text: %r" % (text,))

def as_date(x):
    """datetime.date from a date, datetime, 'YYYY-MM-DD[...]' text, 'Thursday, May 18, 2023' text, or the phone
    clock result dict. Duck-typed, so it also accepts frozen/fake date objects."""
    if isinstance(x, dict) and "date" in x:
        x = x["date"]
    if hasattr(x, "year") and hasattr(x, "month") and hasattr(x, "day"):
        return datetime.date(x.year, x.month, x.day)
    s = str(x).strip()
    try:
        return parse_long_date(s)
    except ValueError:
        pass
    d = parse_dt(s)
    return datetime.date(d.year, d.month, d.day)

def iso(x):
    """'YYYY-MM-DD' text of any date-like value (see as_date)."""
    return as_date(x).isoformat()

def day_range(date_text):
    """Full-day bounds (start, end) as 'YYYY-MM-DDT00:00:00' and 'YYYY-MM-DDT23:59:59' for any date-like value."""
    d = as_date(date_text).isoformat()
    return d + "T00:00:00", d + "T23:59:59"

def shift_days(date_text, days):
    """ISO text 'YYYY-MM-DD' of any date-like value shifted by `days` (negative = earlier)."""
    return (as_date(date_text) + datetime.timedelta(days=days)).isoformat()

def month_start(date_text, months_back=0):
    """ISO text of the first day of the month `months_back` months before the month of date_text."""
    d = as_date(date_text)
    idx = d.year * 12 + (d.month - 1) - months_back
    return datetime.date(idx // 12, idx % 12 + 1, 1).isoformat()

def in_range(ts, start, end):
    """True if timestamp text `ts` lies in [start, end] (each a date or timestamp; a bare end date includes the
    whole day)."""
    t = parse_dt(ts)
    s = parse_dt(start)
    e_text = str(end).strip()
    e = parse_dt(e_text)
    if len(e_text) == 10:
        e = e + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
    return s <= t <= e

def _cell(value):
    text = "" if value is None else str(value)
    if any(c in text for c in [",", '"', "\n", "\r"]):
        text = '"' + text.replace('"', '""') + '"'
    return text

def to_csv(rows, columns):
    """CSV text with a header line then one line per row (a dict read by column name, or a list/tuple in column
    order), using only `columns`. Lines end with \\n."""
    nl = chr(10)
    lines = [",".join(_cell(c) for c in columns)]
    for row in rows:
        if isinstance(row, dict):
            lines.append(",".join(_cell(row.get(c)) for c in columns))
        else:
            lines.append(",".join(_cell(v) for v in list(row)[:len(columns)]))
    return nl.join(lines) + nl

def labeled_amount(text, label):
    """Number following '<label> =>' (optional $) in text, e.g. a 'Total Amount =>' line. Raises if the label
    is missing, so you never fall back to the first number in the file (often a year)."""
    m = re.search(re.escape(label) + r"\s*(?:=>|:|=)\s*\$?\s*(-?[0-9][0-9,]*(?:\.[0-9]+)?)", str(text), re.I)
    if not m:
        raise ValueError("label %r not found" % (label,))
    return float(m.group(1).replace(",", ""))

def sum_labeled(texts, label):
    """Sum of labeled_amount over file contents; texts without the label are skipped (count printed)."""
    total, skipped = 0.0, 0
    for t in texts:
        try:
            total += labeled_amount(t, label)
        except ValueError:
            skipped += 1
    if skipped:
        print("sum_labeled: %d text(s) had no %r line" % (skipped, label))
    return total

def amounts_in(text):
    """All dollar amounts like $12 or $1,234.50 in text, as floats."""
    return [float(m.replace(",", "")) for m in re.findall(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)", str(text))]

def ym(ts):
    """(year, month) of a date or timestamp (text/date); compare tuples for 'this year' / 'last month' filters."""
    d = parse_dt(ts)
    return d.year, d.month

def path_parts(path):
    """(directory, file_name, stem, extension_without_dot) of a path text; directory has no trailing slash."""
    p = str(path).rstrip("/")
    head, _, name = p.rpartition("/")
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    return head, name, stem, ext

def same_path(a, b):
    """True if two path texts name the same location (ignores a trailing slash, '//' and a leading '~/' vs '/')."""
    def n(p):
        p = re.sub(r"/+", "/", str(p).strip())
        return p.rstrip("/") or "/"
    return n(a) == n(b)

def name_ym(path):
    """(year, month) taken from a file NAME such as 'bill_2023-05.txt' or '2023_05_internet.txt'; None if the name
    has no YYYY-MM / YYYY_MM pattern. A bill's billing period is its name, not its created_at (which lags)."""
    name = path_parts(path)[1]
    m = re.search(r"((?:19|20)\d\d)[-_.]?(0[1-9]|1[0-2])(?!\d)", name)
    return (int(m.group(1)), int(m.group(2))) if m else None

def req_state(req):
    """'approved', 'denied' or 'pending' for a payment-request dict, from its approved_at / denied_at fields."""
    if req.get("approved_at"):
        return "approved"
    if req.get("denied_at"):
        return "denied"
    return "pending"

def contacts_by_relationship(contact_callable, relationship, **kwargs):
    """Contacts whose `relationships` LIST contains `relationship` (pass the contact-search callable + token)."""
    rows = fetch_all(contact_callable, relationship=relationship, **kwargs)
    return [c for c in rows if relationship in (c.get("relationships") or [])] or rows

def has_exact_email(user_rows, email):
    """True only if some row's 'email' equals `email` (case-insensitive); user search is fuzzy."""
    return any(norm(r.get("email")) == norm(email) for r in user_rows)

def clock_date(clock_result):
    """datetime.date from the phone clock API result dict (its 'date' text, e.g. 'Thursday, May 18, 2023')."""
    return as_date(clock_result)

def usable_cards(cards, today_date):
    """Cards not expired on today_date; unknown expiry keeps the card. Try them in order."""
    t = as_date(today_date)
    out = []
    for c in cards:
        y, m = c.get("expiry_year"), c.get("expiry_month")
        if y is None or m is None or (int(y), int(m)) >= (t.year, t.month):
            out.append(c)
    return out

def names_of(items, key="name", sep="|"):
    """Join the `key` of each dict (or plain string) of a list with `sep`: a song's artists -> 'A|B'."""
    out = []
    for it in items or []:
        v = it.get(key) if isinstance(it, dict) else it
        if v is not None:
            out.append(str(v))
    return sep.join(out)

def show(obj, limit=3000):
    """Print obj as compact JSON cut at `limit` characters."""
    try:
        text = json.dumps(obj, default=str)
    except Exception:
        text = str(obj)
    print(text if len(text) <= limit else text[:limit] + " ...[cut %d chars]" % (len(text) - limit))
