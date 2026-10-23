"""Generic AppWorld REPL helpers. App and API names are always passed in as arguments."""
import json
import re
import datetime as _dt


def call_api(apis, app, api, **kwargs):
    """call_api(apis, 'APP', 'API', x=1) == apis.APP.API(x=1)."""
    return getattr(getattr(apis, app), api)(**kwargs)


def safe_call(apis, app, api, **kwargs):
    """Return (True, result) or (False, error_text); never raises."""
    try:
        return True, call_api(apis, app, api, **kwargs)
    except Exception as e:
        return False, str(e)[:500]


def fetch_all(apis, app, api, page_limit=20, max_pages=200, **kwargs):
    """Collect every page of a paginated list API (page_index 0,1,2,... until an empty page).
    Pass access_token=... in kwargs ONLY if that API's doc lists it. Returns a flat list."""
    out = []
    for page in range(max_pages):
        res = call_api(apis, app, api, page_index=page, page_limit=page_limit, **kwargs)
        if not isinstance(res, list):
            return res
        if not res:
            break
        out.extend(res)
    return out


def fetch_details(apis, app, api, ids, id_param, **kwargs):
    """Call a detail API once per id, e.g. fetch_details(apis,'APP','show_x',[1,2],'x_id').
    Returns {id: result}; ids whose call fails map to None."""
    out = {}
    for i in ids:
        ok, res = safe_call(apis, app, api, **{id_param: i}, **kwargs)
        out[i] = res if ok else None
    return out


def find_password(passwords, app):
    """passwords = list returned by the supervisor password API. Returns the password for `app`."""
    for p in passwords:
        if p.get("account_name") == app:
            return p.get("password")
    raise ValueError("no password entry for " + str(app))


def peek(x, n=2, width=1500):
    """Print a compact view of a list/dict: its length, the keys of an item and the first n items."""
    if isinstance(x, list):
        print("list of", len(x))
        if x and isinstance(x[0], dict):
            print("keys:", sorted(x[0].keys()))
        print(json.dumps(x[:n], default=str)[:width])
    elif isinstance(x, dict):
        print("keys:", sorted(x.keys()))
        print(json.dumps(x, default=str)[:width])
    else:
        print(repr(x)[:width])


def where(items, **conds):
    """Items whose fields equal the given values. A list field matches if it contains the value;
    strings compare case-insensitively. where(items, genre='x')."""
    def eq(a, b):
        if isinstance(a, list):
            return any(eq(v, b) for v in a)
        if isinstance(a, str) and isinstance(b, str):
            return a.strip().lower() == b.strip().lower()
        return a == b
    return [it for it in items if all(eq(it.get(k), v) for k, v in conds.items())]


def text_match(items, needle, *keys):
    """Items where `needle` occurs (case-insensitive) in any of the given string fields."""
    n = needle.lower()
    return [it for it in items if any(n in str(it.get(k, "")).lower() for k in keys)]


def parse_dt(s):
    """Parse 'YYYY-MM-DD', 'YYYY-MM-DDTHH:MM:SS' or 'YYYY-MM-DD HH:MM:SS' (optional Z/.ffffff) to datetime."""
    s = str(s).strip().replace("Z", "")
    s = s.split(".")[0].replace(" ", "T")
    if "T" not in s:
        s += "T00:00:00"
    return _dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")


def day_bounds(day):
    """(start, end) datetimes covering the whole calendar day of `day` (datetime or string)."""
    d = parse_dt(day) if isinstance(day, str) else day
    start = d.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + _dt.timedelta(days=1) - _dt.timedelta(seconds=1)


def month_bounds(year, month):
    """(first moment, last moment) of a calendar month."""
    start = _dt.datetime(year, month, 1)
    nxt = _dt.datetime(year + (month == 12), month % 12 + 1, 1)
    return start, nxt - _dt.timedelta(seconds=1)


def last_month_bounds(today):
    """Bounds of the calendar month before `today`'s month (today = datetime or string)."""
    t = parse_dt(today) if isinstance(today, str) else today
    y, m = (t.year - 1, 12) if t.month == 1 else (t.year, t.month - 1)
    return month_bounds(y, m)


def in_range(ts, start, end):
    """True if timestamp string/datetime ts lies in [start, end]."""
    t = parse_dt(ts) if isinstance(ts, str) else ts
    return start <= t <= end


def money(x):
    """Extract a float amount from text such as '$1,234.50' (None if no number)."""
    m = re.search(r"-?\d[\d,]*\.?\d*", str(x))
    return float(m.group(0).replace(",", "")) if m else None


def parse_long_date(text):
    """Parse text like 'Thursday, May 18, 2023' (the phone clock's date field) into a datetime."""
    return _dt.datetime.strptime(str(text).strip(), "%A, %B %d, %Y")


def contacts_by_rel(apis, app, api, relationship, **kwargs):
    """All contacts having `relationship`, e.g. contacts_by_rel(apis, APP, API, 'roommate', access_token=tok).
    Returns a list of contact dicts; use {c['email'].lower() for c in result} to match people elsewhere."""
    return fetch_all(apis, app, api, relationship=relationship, **kwargs)


def exact_match(items, **fields):
    """Items whose given fields equal the values exactly (case-insensitive, stripped).
    Use after a fuzzy search: exact_match(results, email='a@b.com')."""
    def norm(v):
        return str(v).strip().lower()
    return [it for it in items if all(norm(it.get(k)) == norm(v) for k, v in fields.items())]


def parse_blocks(content):
    """Split note/file text into records: blank-line separated blocks, first line = 'title',
    following ' - key: value' lines become keys. Returns a list of dicts."""
    out = []
    for block in re.split(r"\n\s*\n", str(content).strip()):
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        rec = {"title": lines[0].strip()}
        for l in lines[1:]:
            m = re.match(r"\s*[-*]?\s*([^:]+):\s*(.*)", l)
            if m:
                rec[m.group(1).strip().lower()] = m.group(2).strip()
        out.append(rec)
    return out


def ids_of(rec):
    """Song ids of a playlist/album/library record: uses rec['song_ids'] or rec['songs'][*]['id'];
    raises KeyError if neither exists (never silently returns an empty list)."""
    if "song_ids" in rec:
        return list(rec["song_ids"])
    if "songs" in rec:
        return [s.get("id", s.get("song_id")) for s in rec["songs"]]
    raise KeyError("record has neither song_ids nor songs: keys=" + str(sorted(rec.keys())))


def union_ids(records):
    """Ordered, de-duplicated list of the song ids of many records (see ids_of)."""
    seen, out = set(), []
    for r in records:
        for i in ids_of(r):
            if i not in seen:
                seen.add(i)
                out.append(i)
    return out


def prefix_through(seq, key, target):
    """Elements of seq up to and including the first whose key(el) == target (error if absent)."""
    out = []
    for el in seq:
        out.append(el)
        if key(el) == target:
            return out
    raise ValueError("target not found in sequence")


def find_by_label(items, text, key="label"):
    """Items whose `key` equals `text` ignoring case and punctuation; raises if none match."""
    def norm(v):
        return re.sub(r"[\W_]+", " ", str(v)).strip().lower()
    out = [it for it in items if norm(it.get(key)) == norm(text)]
    if not out:
        raise KeyError("no item with " + key + " ~ " + str(text))
    return out


def shift_hhmm(t, minutes):
    """Shift an 'HH:MM' string by minutes (wraps around midnight)."""
    h, m = [int(x) for x in t.split(":")]
    tot = (h * 60 + m + minutes) % 1440
    return "%02d:%02d" % (tot // 60, tot % 60)


def title_to_filename(title, ext=""):
    """Whitespace -> '_' only; every other character is kept."""
    return re.sub(r"\s+", "_", str(title).strip()) + ext


def labeled_amount(text, label="Total Amount"):
    """Number after '<label> => $N' (or ':'/'=') in text; None if the label is absent."""
    m = re.search(re.escape(label) + r"\s*(?:=>|=|:)\s*\$?\s*([\d,]+(?:\.\d+)?)", str(text))
    return float(m.group(1).replace(",", "")) if m else None
