"""Generic AppWorld helpers. Pass API functions / app objects in; nothing here is app specific."""
import re
import json
import math
import datetime as _dt
import itertools
import collections
import functools

MONTHS = "january february march april may june july august september october november december"

def paged(fn, page_limit=20, max_pages=100, **kw):
    """Collect ALL items of a paginated list API: paged(apis.X.some_list_api, access_token=tok, query='abc').
    Starts at page_index=0, uses the largest page size, stops only on an empty page (never on a short page).
    kwargs whose value is None are dropped.
    If the API has no paging parameters (error mentions page_index/page_limit) it is called once instead."""
    out = []
    i = 0
    kw = {k: v for k, v in kw.items() if v is not None}  # a None kwarg (e.g. relationship=None) breaks calls
    while max_pages is None or i < max_pages:
        args = dict(kw, page_index=i)
        if page_limit:
            args["page_limit"] = page_limit
        try:
            page = fn(**args)
        except Exception as e:  # noqa: BLE001
            if i == 0 and ("page_index" in str(e) or "page_limit" in str(e)):
                page = fn(**kw)
                if isinstance(page, dict):
                    return [page]
                return list(page)
            raise
        if isinstance(page, dict):
            raise ValueError("expected a list page, got dict with keys %s" % list(page))
        if not page:
            break
        out.extend(page)
        i += 1
    return out

def password_of(passwords, account_name):
    """Password for one account from the supervisor password list (matches account_name exactly)."""
    for p in passwords:
        if p.get("account_name") == account_name:
            return p["password"]
    raise KeyError("no password for %r; have %s" % (account_name, [p.get("account_name") for p in passwords]))

def token_of(login_fn, username, password):
    """token_of(apis.X.login, username, password) -> access_token string (raises on failure)."""
    r = login_fn(username=username, password=password)
    return r["access_token"]

def peek(x, n=1200):
    """Print the shape of a value: type, length, keys of the first item, then a truncated JSON dump."""
    if isinstance(x, list):
        print("list len=%d" % len(x), "first item keys:", list(x[0]) if x and isinstance(x[0], dict) else type(x[0]).__name__ if x else None)
    elif isinstance(x, dict):
        print("dict keys:", list(x))
    s = json.dumps(x, indent=1, default=str)
    print(s[:n] + (" ...[truncated]" if len(s) > n else ""))

def parse_day(s):
    """Parse 'Thursday, May 18, 2023', '2023-05-18', '2023-05-18T10:00:00' or a datetime/date -> _dt.date."""
    if isinstance(s, _dt.datetime):
        return s.date()
    if isinstance(s, _dt.date):
        return s
    if isinstance(s, dict):
        s = s.get("date") or s.get("datetime") or next(iter(s.values()))
    s = str(s).strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", s)
    if m and m.group(1).lower() in MONTHS.split():
        return _dt.date(int(m.group(3)), MONTHS.split().index(m.group(1).lower()) + 1, int(m.group(2)))
    raise ValueError("cannot parse date %r" % s)

def same_day(ts, day):
    """True if timestamp string ts (e.g. '2023-05-18T09:12:00') falls on date `day`."""
    return str(ts)[:10] == parse_day(day).isoformat()

def day_span(day):
    """(start, end) strings 'YYYY-MM-DDT00:00:00' and 'YYYY-MM-DDT23:59:59' for a whole day."""
    d = parse_day(day).isoformat()
    return d + "T00:00:00", d + "T23:59:59"

def month_span(day, offset=0):
    """(first_date, last_date) of the calendar month `offset` months from day's month (-1 = last month)."""
    d = parse_day(day)
    idx = d.year * 12 + d.month - 1 + offset
    first = _dt.date(idx // 12, idx % 12 + 1, 1)
    nxt = idx + 1
    last = _dt.date(nxt // 12, nxt % 12 + 1, 1) - _dt.timedelta(days=1)
    return first, last

def week_span(day, offset=0):
    """(Monday, Sunday) of the ISO week `offset` weeks from day's week (-1 = last week)."""
    d = parse_day(day) + _dt.timedelta(weeks=offset)
    mon = d - _dt.timedelta(days=d.weekday())
    return mon, mon + _dt.timedelta(days=6)

def in_span(ts, first, last):
    """True if the date part of ts lies in [first, last] (dates inclusive)."""
    return parse_day(first) <= parse_day(ts) <= parse_day(last)

def norm(s):
    """Lowercase, '-' and '_' to space, collapse whitespace; for comparing labels like 'Co-worker'."""
    return re.sub(r"\s+", " ", str(s).lower().replace("-", " ").replace("_", " ")).strip()

def has_rel(contact, rel):
    """True if the contact's relationships list contains rel (normalized, exact words)."""
    rels = contact.get("relationships")
    if rels is None:
        rels = [contact.get("relationship")]
    if isinstance(rels, str):
        rels = [rels]
    return norm(rel) in [norm(r) for r in rels if r]

def song_ids(x):
    """Song ids (ints) from ANY of: a list of ids / items; a song-library item (singular song_id);
    a playlist/album library item (song_ids); a detail view (songs[].id or songs[].song_id).
    Lists of such items are flattened (order kept, duplicates kept; use dedupe() to dedupe).
    Raises if the shape is unknown, so a wrong shape is never silently an empty list."""
    if isinstance(x, (list, tuple)):
        out = []
        for it in x:
            out.extend(song_ids(it))
        return out
    if isinstance(x, int):
        return [x]
    if isinstance(x, dict):
        if x.get("song_ids") is not None:
            return list(x["song_ids"])
        if x.get("songs") is not None:
            return [s["id"] if "id" in s else s["song_id"] for s in x["songs"]] if x["songs"] and isinstance(x["songs"][0], dict) else list(x["songs"])
        if "song_id" in x:
            return [x["song_id"]]
    raise ValueError("song_ids: unknown shape, keys=%s" % (list(x) if isinstance(x, dict) else type(x).__name__))

def money(s):
    """'$1,234.50' / 'USD 12' / 12 -> float."""
    if isinstance(s, (int, float)):
        return float(s)
    m = re.search(r"-?\d[\d,]*\.?\d*", str(s))
    if not m:
        raise ValueError("no number in %r" % s)
    return float(m.group(0).replace(",", ""))

def amounts(text):
    """All money-like numbers in a text, as (line, value) pairs, for READING a receipt. Never sum these values
    (they include line items and totals): for a bill use bill_total(text) / sum_bill_totals(...)."""
    out = []
    for line in str(text).splitlines():
        for m in re.finditer(r"\$\s*(\d[\d,]*\.?\d*)", line):
            out.append((line.strip(), float(m.group(1).replace(",", ""))))
    return out

def split_evenly(total, n):
    """Equal share of total among n people, rounded to cents."""
    return round(float(total) / n, 2)

def dedupe(items, key=lambda x: x):
    """Remove duplicates, keep first occurrence and original order."""
    seen, out = set(), []
    for it in items:
        k = key(it)
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out

def top_by(items, key, n=1, largest=True):
    """Items with the n best values of key, ties kept (so a 'most/least' question shows ties)."""
    vals = sorted({key(i) for i in items}, reverse=largest)[:n]
    return [i for i in items if key(i) in vals]

def csv_rows(rows, header=None, sep=","):
    """Plain CSV text: fields joined by sep, NO quoting; header optional; one row per line."""
    lines = [sep.join(header)] if header else []
    for r in rows:
        if isinstance(r, dict):
            if not header:
                raise ValueError("dict rows need header=[column names]")
            r = [r[h] for h in header]
        elif isinstance(r, str):
            raise ValueError("a row must be a list or dict, got str %r" % r)
        lines.append(sep.join(str(c) for c in r))
    return "\n".join(lines)

def sandbox_today(date_fn):
    """sandbox_today(apis.<phone app>.<get-date-and-time api>) -> a DATE object (not a dict, not a string): use
    today.year / .month / .day, str(today) = 'YYYY-MM-DD', shift_day, month_span. It is NOT subscriptable
    (no today['date'], no today[:4]) and has no .split()."""
    return parse_day(date_fn())

def shift_day(day, n):
    """The date n days after `day` (n=-1 is yesterday). Accepts anything parse_day accepts."""
    return parse_day(day) + _dt.timedelta(days=n)

def same_month(ts, day):
    """True if ts falls in the same calendar YEAR AND month as `day` (month alone is not enough)."""
    a, b = parse_day(ts), parse_day(day)
    return (a.year, a.month) == (b.year, b.month)

def file_for_month(paths, day):
    """The paths whose file name mentions the month (and year, when the name has one) of `day`.
    Matches 'may', '2023-05', '05-2023', 'may_2023'. Returns a list; print it and check it has what you expect."""
    d = parse_day(day)
    name = MONTHS.split()[d.month - 1]
    short = name[:3]
    out = []
    for p in paths:
        base = norm(str(p).rpartition("/")[2])
        years = re.findall(r"20\d\d", base)
        if years and str(d.year) not in years:
            continue
        iso = re.search(r"20\d\d[ \-/.]?(\d{2})", base)
        by_num = iso and int(iso.group(1)) == d.month
        by_name = re.search(r"\b(%s|%s)\b" % (name, short), base)
        if by_num or by_name:
            out.append(p)
    return out

def bill_total(text):
    """The amount on the line labelled 'Total' (the last such line) of a bill/receipt text. Raises if none.
    Ignores line items, subtotals and tax; print the text once to be sure that is what the task means."""
    best = None
    for line in str(text).splitlines():
        if re.search(r"\btotal\b", line, re.I) and not re.search(r"sub\s*total", line, re.I):
            m = re.search(r"\$?\s*(\d[\d,]*\.?\d*)\s*$", line.strip())
            if m:
                best = float(m.group(1).replace(",", ""))
    if best is None:
        raise ValueError("no 'Total' line with an amount; print the text and read it")
    return best

def contacts_with_rel(contacts, rel):
    """Contacts having relationship rel. 'sibling' also matches brother and sister; 'parent' matches mother/father;
    'child' matches son/daughter; 'spouse' matches husband/wife. Print the result and its relationship labels."""
    groups = {"sibling": ["sibling", "brother", "sister"], "parent": ["parent", "mother", "father"],
              "child": ["child", "son", "daughter"], "spouse": ["spouse", "husband", "wife"]}
    labels = groups.get(norm(rel), [rel])
    return [c for c in contacts if any(has_rel(c, l) for l in labels)]

def pay_with_any_card(create_fn, card_ids, **kw):
    """Call create_fn(payment_card_id=<id>, **kw) for each card id until one works; returns (card_id, result).
    Use when a send fails for insufficient funds/balance: do NOT add money to the balance, try another card."""
    errs = []
    for c in card_ids:
        try:
            return c, create_fn(payment_card_id=c, **kw)
        except (TypeError, ValueError, KeyError):
            raise
        except Exception as e:  # noqa: BLE001
            errs.append((c, str(e)[:100]))
    raise RuntimeError("no card worked: %s" % errs)

def played_so_far(queue_items):
    """Queue items (dicts with 'position' and 'is_current') at or before the current song, in order."""
    cur = [q["position"] for q in queue_items if q.get("is_current")]
    if not cur:
        raise ValueError("no item has is_current=True; print the queue")
    return [q for q in queue_items if q["position"] <= cur[0]]

def add_minutes(hhmm, n):
    """'HH:MM' (24h) plus n minutes (n may be negative) -> 'HH:MM', wrapping around midnight."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(hhmm).strip())
    if not m:
        raise ValueError("add_minutes wants 'HH:MM' (24h), got %r" % hhmm)
    t = (int(m.group(1)) * 60 + int(m.group(2)) + int(n)) % 1440
    return "%02d:%02d" % (t // 60, t % 60)

def split_path(path):
    """'a/b/c.txt' -> ('a/b', 'c.txt'). Use instead of the blocked os.path."""
    return str(path).rpartition("/")[0], str(path).rpartition("/")[2]

def join_path(*parts):
    """join_path('~/a/', '/b', 'c.txt') -> '~/a/b/c.txt'. Use instead of the blocked os.path.join."""
    parts = [str(p) for p in parts if p]
    return "/".join([parts[0].rstrip("/")] + [p.strip("/") for p in parts[1:]]) if parts else ""

def has_account(search_users_fn, email, **kw):
    """True only if a result has EXACTLY this email (user searches are fuzzy: non-empty proves nothing)."""
    users = paged(search_users_fn, query=email, **kw)
    return any(str(u["email"]).lower() == str(email).lower() for u in users)

def note_items(content):
    """Parse note text of blocks 'Title' + ' - key: value' lines -> [{'title': ..., key: value}] (keys lower-cased).
    Lines without 'key: value' start a new item. Print the result and check the keys you filter on."""
    items, cur = [], None
    for line in str(content).splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^[-*]\s*([^:]+):\s*(.*)$", s)
        if m:
            if cur is None:
                raise ValueError("attribute line before any title: %r" % s)
            cur[norm(m.group(1))] = m.group(2).strip()
        else:
            cur = {"title": s}
            items.append(cur)
    return items

def show_thread(search_messages_fn, phone_number, access_token, **kw):
    """Whole text conversation with one phone number, oldest first (paginated fully); prints every message."""
    msgs = paged(search_messages_fn, phone_number=phone_number, access_token=access_token, **kw)
    msgs = sorted(msgs, key=lambda m: m["sent_at"])
    for m in msgs:
        print(m["sent_at"], m["sender"]["name"], "->", m["receiver"]["name"], ":", m["message"])
    return msgs

def songs_by_artist(search_songs_fn, artist_id, **kw):
    """ALL songs of one artist id (paged search with artist_id; keeps items whose artists[] has that id)."""
    return [s for s in paged(search_songs_fn, artist_id=artist_id, **kw) if any(a["id"] == artist_id for a in s["artists"])]

def set_song_rating(list_reviews_fn, create_fn, update_fn, song_id, rating, user_email, access_token):
    """Give song_id MY rating: update my existing review, else create one (creating twice fails with 409).
    list_reviews_fn=show-song-reviews api, create_fn=review-song api, update_fn=update-song-review api.
    Returns ('updated'|'created', result). Check beforehand that the task wants this song changed."""
    mine = paged(list_reviews_fn, song_id=song_id, user_email=user_email)
    if mine:
        return "updated", update_fn(review_id=mine[0]["song_review_id"], rating=rating, access_token=access_token)
    return "created", create_fn(song_id=song_id, rating=rating, access_token=access_token)

def sum_bill_totals(show_file_fn, paths, access_token, ext=".txt"):
    """Sum of the 'Total' line over the bill files in `paths`, counting a .pdf/.txt pair of the same bill once
    (reads only `ext` files). Prints every file and its total; returns the sum."""
    seen, total = set(), 0.0
    for p in sorted(paths):
        stem, dot, e = str(p).rpartition(".")
        if dot + e != ext or stem in seen:
            continue
        seen.add(stem)
        v = bill_total(show_file_fn(file_path=p, access_token=access_token)["content"])
        print(p, v)
        total += v
    assert seen, "no %s files in paths; print the listing" % ext
    print("bills counted:", len(seen), "sum:", round(total, 2))
    return round(total, 2)

def items_where(items, **want):
    """Keep dict items whose field equals (or lists, split on , / ; &) the wanted value, compared with norm().
    items_where(note_items(text), genre='action', director='x'). A value may be a list (any of). Prints kept/total;
    0 kept means a wrong key or value: print the items."""
    def ok(it, k, v):
        have = [norm(p) for p in re.split(r"[,/;&]", str(it.get(norm(k), "")))]
        return any(norm(w) in have for w in (v if isinstance(v, (list, tuple, set)) else [v]))
    out = [it for it in items if all(ok(it, k, v) for k, v in want.items())]
    print("items_where kept %d of %d" % (len(out), len(items)))
    return out

def load_songs(show_song_fn, ids):
    """{song_id: full show_song record} for the deduped ids (genre, release_date, play_count, rating live only
    here; list/recommendation/library items are slim). Use after song_ids(...)."""
    return {i: show_song_fn(song_id=i) for i in dedupe(ids)}

def weekday_name(day):
    """'Monday'... for any date parse_day accepts."""
    return parse_day(day).strftime("%A")

def export_name(title, ext=".md"):
    """File name for a note title: EACH whitespace character -> '_', every other character kept (no sanitizing)."""
    return re.sub(r"\s", "_", str(title)) + ext
