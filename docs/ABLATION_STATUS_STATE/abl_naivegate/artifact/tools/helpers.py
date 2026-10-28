"""Generic REPL helpers (apis and app/API names are ARGUMENTS). Optional: write your own code if one does not fit."""
import re
import json
import math
import datetime as _dt
import itertools
import collections
import functools


def fetch_all_pages(apis, app_name, api_name, page_limit=20, max_pages=300, **kwargs):
    """Call a paginated list API for EVERY page (page_index=0,1,... with page_limit, max 20; the API default is only 5) and
    return one flat list; stops at the first empty page. Example: fetch_all_pages(apis, '<app>', '<list_api>', access_token=t)
    Extra keyword arguments are passed through; None and '' values are dropped (they can make an API return 0 results).
    An empty list can be real or a wrong filter - print len() and a sample before relying on it."""
    fn = getattr(getattr(apis, app_name), api_name)
    kwargs = {k: v for k, v in kwargs.items() if v is not None and v != ''}
    page_limit = min(int(page_limit or 20), 20)
    items = []
    prev = None
    for page_index in range(int(max_pages or 300)):
        page = fn(page_index=page_index, page_limit=page_limit, **kwargs)
        if not page:
            break
        if isinstance(page, dict):
            raise ValueError("API returned a dict, not a list; it is not a paginated list API: %r" % (page,))
        if page == prev:
            break
        prev = page
        items.extend(page)
        if len(page) < page_limit:
            break
    return items


def get_ids(items, *field_names):
    """Collect ids from a list of dicts, trying each field name in order per item
    (e.g. get_ids(songs, 'song_id', 'id')). With no field names it tries 'id' then any key ending in '_id'.
    Items may also be plain ints. Returns a list (order kept, duplicates kept).
    RAISES if items is non-empty but no id could be extracted (a wrong field name must not look like 'no data')."""
    out = []
    for it in items:
        if isinstance(it, dict):
            names = field_names or (["id"] + [k for k in it if str(k).endswith("_id")])
            for f in names:
                if it.get(f) is not None:
                    out.append(it[f])
                    break
        elif it is not None:
            out.append(it)
    if items and not out:
        raise ValueError("get_ids: no ids found with fields %r; item keys are %s" % (
            field_names, sorted(items[0].keys()) if isinstance(items[0], dict) else type(items[0]).__name__))
    return out


def require_fields(items, *fields):
    """Raise (listing the actual keys) unless the first items carry every named field, so a hallucinated field name fails
    loudly instead of matching nothing. Returns items unchanged. Example: items = require_fields(items, 'release_date')."""
    for it in list(items)[:3]:
        if not isinstance(it, dict):
            raise ValueError("require_fields: item is %s, not dict: %s" % (type(it).__name__, str(it)[:80]))
        missing = [f for f in fields if f not in it]
        if missing:
            raise ValueError("require_fields: %s missing; actual keys: %s" % (missing, sorted(it.keys())))
    return items


def parse_dt(value):
    """Parse an ISO-like timestamp or date string ('2023-05-18T09:26:00', '2023-05-18', '2023-05-18 09:26:00')
    or the phone app's date text ('Thursday, May 18, 2023') into a datetime. Returns None if it cannot be parsed."""
    if isinstance(value, _dt.datetime):
        return value
    if isinstance(value, _dt.date):
        return _dt.datetime(value.year, value.month, value.day)
    s = str(value).strip().replace("Z", "")
    s = s.split(".")[0] if "T" in s or " " in s else s
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M", "%A, %B %d, %Y"):
        try:
            return _dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def date_window(period, today=None, n=None):
    """Inclusive ('YYYY-MM-DD', 'YYYY-MM-DD') for: today, yesterday, this_week (Mon-today), last_week (Mon-Sun), this_month,
    last_month, this_year, last_year, last_n_days (needs n; INCLUDES today), last_n_days_excluding_today (needs n).
    today: date/string (the phone app's date text works); pass the app's date, not the real one.
    Example: lo, hi = date_window('last_month'); then use `lo <= created_at[:10] <= hi`."""
    t = parse_dt(today) if today is not None else _dt.datetime.now()
    d = t.date()
    one = _dt.timedelta(days=1)
    if period == "today":
        a, b = d, d
    elif period == "yesterday":
        a, b = d - one, d - one
    elif period == "this_week":
        a, b = d - _dt.timedelta(days=d.weekday()), d
    elif period == "last_week":
        mon = d - _dt.timedelta(days=d.weekday())
        a, b = mon - _dt.timedelta(days=7), mon - one
    elif period == "this_month":
        a, b = d.replace(day=1), d
    elif period == "last_month":
        first = d.replace(day=1)
        b = first - one
        a = b.replace(day=1)
    elif period == "this_year":
        a, b = d.replace(month=1, day=1), d
    elif period == "last_year":
        a, b = _dt.date(d.year - 1, 1, 1), _dt.date(d.year - 1, 12, 31)
    elif period == "last_n_days":
        if not n:
            raise ValueError("last_n_days needs n")
        a, b = d - _dt.timedelta(days=int(n) - 1), d
    elif period == "last_n_days_excluding_today":
        if not n:
            raise ValueError("last_n_days_excluding_today needs n")
        a, b = d - _dt.timedelta(days=int(n)), d - one
    else:
        raise ValueError("unknown period %r; valid: today, yesterday, this_week, last_week, this_month, "
                         "last_month, this_year, last_year, last_n_days, last_n_days_excluding_today" % (period,))
    return a.isoformat(), b.isoformat()


def in_window(timestamp, start_date, end_date):
    """True if the date part of `timestamp` lies in [start_date, end_date] (inclusive, 'YYYY-MM-DD')."""
    dt = parse_dt(timestamp)
    if dt is None:
        return False
    return start_date <= dt.date().isoformat() <= end_date


def top_n(items, key, n=1, largest=True):
    """Return the n items with the largest (or smallest) numeric `key` (field name or function).
    Items whose key is missing/None are an ERROR (raises) instead of silently counting as 0 -
    that mistake (reading a field the API does not return) caused wrong answers before.
    Ties: all items tied with the n-th value are also returned, so check len(result) > n for a tie."""
    getter = key if callable(key) else (lambda x: x.get(key))
    vals = []
    for it in items:
        v = getter(it)
        if v is None:
            raise ValueError("top_n: key %r missing on item %s -- fetch the right detail API for that field first"
                             % (key if not callable(key) else "<fn>", str(it)[:120]))
        vals.append((v, it))
    vals.sort(key=lambda p: p[0], reverse=largest)
    if not vals:
        return []
    n = max(1, int(n))
    cutoff = vals[min(n, len(vals)) - 1][0]
    return [it for v, it in vals if (v >= cutoff if largest else v <= cutoff)]


def call_each(fn, arg_list, id_arg, **common):
    """Call fn(<id_arg>=x, **common) for every x in arg_list. Never stops on an error:
    returns a TUPLE (results, errors) where results is {x: response} and errors is {x: error text}.
    Always unpack it: results, errors = call_each(...)  (never index the tuple as if it were the dict).
    Use for bulk actions (like / follow / delete many) so that one 'already done' error does not
    abort the loop. Print the errors afterwards and judge whether they matter."""
    results, errors = {}, {}
    for x in arg_list:
        try:
            results[x] = fn(**{id_arg: x}, **common)
        except Exception as e:  # noqa: BLE001
            errors[x] = str(e)[:200]
    return results, errors


def norm_text(s):
    """Lowercase, strip, collapse whitespace - for comparing names/titles/labels."""
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def make_csv(rows, header=None):
    """Build CSV text (header line first if given, one line per row, '\\n' separated, no trailing blank line).
    Cells containing a comma, quote or newline are quoted.
    rows: list of lists/tuples, OR list of dicts (then header defaults to the first row's keys and cells follow
    header order). A row that is a plain string raises (it would be split into characters)."""
    rows = list(rows)
    if rows and all(isinstance(r, dict) for r in rows):
        header = header or list(rows[0].keys())
        rows = [[r.get(h) for h in header] for r in rows]
    for r in rows:
        if isinstance(r, (str, bytes)) or not hasattr(r, "__iter__"):
            raise ValueError("make_csv: each row must be a list/tuple/dict, got %r" % (r,))
    def cell(v):
        t = "" if v is None else str(v)
        if any(c in t for c in ',"\n'):
            t = '"' + t.replace('"', '""') + '"'
        return t
    lines = []
    if header:
        lines.append(",".join(cell(h) for h in header))
    for r in rows:
        lines.append(",".join(cell(v) for v in r))
    return "\n".join(lines)


def read_thread(apis, app_name, api_name, show=True, **kwargs):
    """Fetch EVERY message of a conversation (all pages), sort oldest -> newest and print '[sent_at] sender -> receiver: message'
    (text is in `message`, there is no `content`). Returns the sorted list.
    Example: msgs = read_thread(apis, '<phone_app>', '<search_messages_api>', access_token=t, phone_number='<number>').
    Obey the LAST message FROM the other person; older ones are context or decoys. Do not pass `query=`."""
    msgs = fetch_all_pages(apis, app_name, api_name, **kwargs)
    require_fields(msgs, "message", "sent_at")
    msgs = sorted(msgs, key=lambda m: str(m.get("sent_at")))
    if show:
        for m in msgs:
            who = lambda p: (p or {}).get("name") or (p or {}).get("phone_number") or "?"
            print("[%s] %s -> %s: %s" % (m.get("sent_at"), who(m.get("sender")), who(m.get("receiver")), m.get("message")))
    return msgs


def parse_blocks(text):
    """Split note text of the form 'Title' / ' - key: value' / ' - key: value' / blank / 'Title'... into records.
    Returns a list of dicts {'title': ..., '<key>': '<value>', ...} (keys lower-cased). Lines starting with '#' are skipped.
    Use it to FILTER entries by a field named in the request (e.g. keep records whose 'director' matches) instead of
    returning every title. Print the records and check the key names before filtering."""
    out, cur = [], None
    for raw in str(text).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^[-*]\s*([^:]+):\s*(.*)$", line)
        if m and cur is not None:
            cur[m.group(1).strip().lower()] = m.group(2).strip()
        elif not m:
            cur = {"title": line}
            out.append(cur)
    return out


def labelled_amount(text, label="total"):
    """Number on the line whose text contains `label` (case-insensitive), e.g. 'Total Amount => $77.00' -> 77.0.
    Returns the LAST such line's amount; None if no line has the label and a number. Never sums other '$' amounts
    (fees, taxes, line items) in the same file. Print one sample file first to confirm the label."""
    found = None
    for line in str(text).splitlines():
        if label.lower() in line.lower():
            nums = re.findall(r"-?\d[\d,]*\.?\d*", line.split(":")[-1] if "=>" not in line else line.split("=>")[-1])
            if nums:
                found = float(nums[-1].replace(",", ""))
    return found


def resolve_names(contacts, names):
    """Map each given name (first name or 'First Last') to EXACTLY ONE contact dict from `contacts` (already filtered to
    the right relationship). Raises, listing the candidates, when a name matches nobody or several people - decide
    explicitly instead of taking the first hit. Returns {name: contact}. Compare people by contact['email'] afterwards."""
    out = {}
    for n in names:
        k = norm_text(n)
        hits = [c for c in contacts if k in (norm_text(c.get("first_name", "")),
                                             norm_text("%s %s" % (c.get("first_name", ""), c.get("last_name", ""))))]
        if len(hits) != 1:
            raise ValueError("resolve_names: %r matched %d contacts: %s" % (
                n, len(hits), [(c.get("first_name"), c.get("last_name"), c.get("relationships")) for c in (hits or contacts)][:8]))
        out[n] = hits[0]
    return out


def txns_with(txns, emails, side="sender"):
    """Keep transactions/payment requests whose `side` ('sender', 'receiver' or 'either') person has an email in `emails`.
    Items carry sender/receiver OBJECTS {name, email}; there is NO 'direction' field on an item (direction is only a query
    argument), and no first_name/last_name. Build `emails` in code from contacts - never type the list by hand."""
    emails = set(emails)
    sides = ("sender", "receiver") if side == "either" else (side,)
    return [t for t in txns if any(((t.get(s) or {}).get("email") in emails) for s in sides)]


def live_cards(cards, today=None):
    """Payment cards (dicts with expiry_year / expiry_month) that are not expired on `today` (default now); a card is valid
    through the end of its expiry month. Cards may still lack funds - use first_success to try them in turn."""
    t = parse_dt(today) if today is not None else _dt.datetime.now()
    return [c for c in cards if (c["expiry_year"], c["expiry_month"]) >= (t.year, t.month)]


def first_success(fn, arg_name, candidates, **common):
    """Call fn(<arg_name>=c, **common) for each candidate in order until one call succeeds; returns the successful
    RESPONSE only (ONE value: resp = first_success(...); do not unpack it) and prints which candidate won and why earlier ones failed.
    A candidate of None means 'omit the argument' (e.g. pay from the balance first, then from each card). Failed calls
    created nothing, so retrying the next candidate is safe; a call that SUCCEEDED is never repeated. Raises with all error
    texts if every candidate fails. Keep this call in a cell of its own: if a later line errors, do NOT re-run the cell
    (read the state first). Example: resp = first_success(fn, 'payment_card_id', [None] + card_ids, receiver_email=e, ...)."""
    errors = {}
    for c in candidates:
        kw = dict(common)
        if c is not None:
            kw[arg_name] = c
        try:
            resp = fn(**kw)
        except Exception as e:  # noqa: BLE001
            errors[c] = str(e)[:160]
            continue
        print("first_success: succeeded with %s=%r; failed before: %r" % (arg_name, c, errors))
        return resp
    raise RuntimeError("first_success: every candidate failed: %r" % (errors,))


def get_token(apis, app_name, supervisor_app):
    """Access token for `app_name`, CACHED: the first call logs in (password from <supervisor_app>.show_account_passwords,
    username = profile email, then phone number); later calls return the same token with no new login. So start every cell
    that calls an app with `tok = get_token(apis, '<app>', '<supervisor_app>')` and never rely on a variable from an earlier cell.
    Raises with the errors if login fails."""
    cache = get_token.__dict__.setdefault("cache", {})
    key = (id(apis), app_name)
    if key in cache:
        return cache[key]
    sup = getattr(apis, supervisor_app)
    pw = [p["password"] for p in sup.show_account_passwords() if p.get("account_name") == app_name]
    if not pw:
        raise ValueError("get_token: no stored password for %r" % (app_name,))
    prof, errs = sup.show_profile(), []
    for user in (prof.get("email"), prof.get("phone_number")):
        try:
            cache[key] = getattr(apis, app_name).login(username=user, password=pw[0])["access_token"]
            return cache[key]
        except Exception as e:  # noqa: BLE001
            errs.append(str(e)[:100])
    raise RuntimeError("get_token: login failed for %r: %r" % (app_name, errs))


def snapshot_dates(apis, app_name, show_api, token, paths, path_arg="file_path"):
    """{path: datetime} of each file's created_at, read BEFORE any move/rename (a move without retain_dates resets created_at
    to now). Raises if a file has no created_at. Example: dates = snapshot_dates(apis, '<fs_app>', '<show_file_api>', tok, paths)."""
    fn, out = getattr(getattr(apis, app_name), show_api), {}
    for p in paths:
        info = fn(access_token=token, **{path_arg: p})
        d = parse_dt(info.get("created_at"))
        if d is None:
            raise ValueError("snapshot_dates: no usable created_at for %s: keys %s" % (p, sorted(info)))
        out[p] = d
    return out


def member_ids(obj):
    """Song ids of a playlist/album/library item, from EITHER shape: library list items carry `song_ids`; detail responses
    carry `songs` (each with `id` or `song_id`). Union of both, order kept, no duplicates. Raises (listing the keys) when
    nothing is found: a 0-song container is almost always the wrong response shape, not a real empty one."""
    out = list(obj.get("song_ids") or []) if isinstance(obj, dict) else []
    for x in (obj.get("songs") or []) if isinstance(obj, dict) else []:
        v = x.get("song_id", x.get("id")) if isinstance(x, dict) else x
        if v is not None:
            out.append(v)
    if not out:
        raise ValueError("member_ids: no song ids; keys are %s" % (sorted(obj) if isinstance(obj, dict) else type(obj).__name__))
    return list(dict.fromkeys(out))


def play_in_container(play_fn, queue_fn, current_fn, token, target_id, **container):
    """Play `target_id` INSIDE its container so the player's collection is right (playing a bare song id leaves the
    collection wrong). container is exactly one of album_id=A / playlist_id=P. Plays the container, finds the target in the
    queue, plays that queue_position, then RAISES unless the current song id equals target_id. Returns the current song.
    Example: play_in_container(play_fn, queue_fn, current_fn, tok, best_id, playlist_id=P)."""
    if len(container) != 1:
        raise ValueError("play_in_container: pass exactly one container keyword (album_id=... or playlist_id=...)")
    play_fn(access_token=token, **container)
    pos = [q["position"] for q in queue_fn(access_token=token) if q.get("song_id") == target_id]
    if not pos:
        raise ValueError("play_in_container: song %r is not in the queue after playing %r" % (target_id, container))
    play_fn(access_token=token, queue_position=pos[-1])
    cur = current_fn(access_token=token)
    if cur.get("song_id", cur.get("id")) != target_id:
        raise ValueError("play_in_container: current song is %r, wanted %r" % (cur.get("song_id", cur.get("id")), target_id))
    return cur


def upsert_review(list_fn, create_fn, update_fn, token, song_id, my_email, **fields):
    """Write MY review of a song exactly once: if show-reviews(song_id, user_email=my_email) already has one, update it
    (its id is the item key `song_review_id`; the update call takes it as review_id=), else create. fields: rating/title/text.
    Never creates a second review. Prints which path was taken and returns the response."""
    found = []
    for pi in range(50):
        page = list_fn(song_id=song_id, user_email=my_email, page_index=pi, page_limit=20)
        found.extend(page or [])
        if not page or len(page) < 20:
            break
    if len(found) > 1:
        raise ValueError("upsert_review: %d reviews match; keys %s" % (len(found), sorted(found[0])))
    if found:
        rid = found[0].get("song_review_id", found[0].get("review_id"))
        if rid is None:
            raise ValueError("upsert_review: no review id in keys %s" % sorted(found[0]))
        print("upsert_review: updating existing review", rid)
        return update_fn(review_id=rid, access_token=token, **fields)
    print("upsert_review: no existing review; creating")
    return create_fn(song_id=song_id, access_token=token, **fields)


def list_paths(show_fn, token, directory_path, recursive=True, entry_type="files", allow_empty=False, **kw):
    """List files (or entry_type='directories'/'all') under directory_path, RECURSIVELY by default, as absolute path strings
    (directories end in '/'). RAISES on an empty result: 0 entries almost always means a wrong path/flag, and summing or
    moving 'nothing' silently fails the task. Pass allow_empty=True only if an empty folder is the real answer."""
    paths = show_fn(access_token=token, directory_path=directory_path, recursive=recursive, entry_type=entry_type, **kw)
    if not paths and not allow_empty:
        raise ValueError("list_paths: 0 entries under %r (recursive=%r, entry_type=%r): check the path, list its parent "
                         "directory first, and prefer recursive=True" % (directory_path, recursive, entry_type))
    return paths
