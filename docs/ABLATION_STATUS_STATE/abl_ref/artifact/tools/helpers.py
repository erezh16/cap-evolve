"""REPL helpers. They take `apis` plus app / API names as parameters; modules use private aliases so agent code
(`from datetime import datetime`, `re = ...`) cannot break them (shared REPL namespace)."""
import re as _re
import json as _json
import math
import datetime as _dt
import itertools
import collections
import functools

_DATE_FORMATS = "%Y-%m-%dT%H:%M:%S.%f|%Y-%m-%dT%H:%M:%S|%Y-%m-%dT%H:%M|%Y-%m-%d %H:%M:%S|%Y-%m-%d|%A, %B %d, %Y %I:%M %p|%A, %B %d, %Y|%B %d, %Y|%b %d, %Y|%m/%d/%Y"
_SAFE_TO_DROP = "access_token page_index page_limit"

def _tok(_store={}):  # app -> token remembered by login_all
    return _store

def _rows(items):
    """Rows of a list or of a {key: row} dict (fetch_each output)."""
    return list(items.values()) if isinstance(items, dict) else list(items or [])

def _api(apis, app_name, api_name):
    try:
        return getattr(getattr(apis, app_name), api_name)
    except Exception as exc:
        try:
            docs = getattr(apis, "api_" + "docs").show_api_descriptions(app_name=app_name)
            names = [d["name"] for d in docs]
        except Exception:
            raise exc
        words = [w for w in _re.split(r"[_\W]+", str(api_name).lower()) if w]
        near = [n for n in names if any(w in n for w in words)] or names
        raise Exception("%s Did you mean one of: %s ? (check show_api_descriptions for the exact name)"
                        % (str(exc).split("\n")[0], near[:12]))

def _allowed_params(exc):
    """Names in an 'Unexpected parameter ... Allowed parameters are: [...]' error, else None."""
    text = str(exc)
    if "Unexpected parameter" not in text:
        return None
    m = _re.search(r"Allowed parameters are:\s*\[([^\]]*)\]", text)
    if not m:
        return None
    return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]

def _call(fn, kw, app=None):
    """fn(**kw). A 401 without access_token is retried once with the token login_all stored for `app`; an
    access_token / page_index / page_limit the API rejects as unexpected is dropped once. Other errors are raised."""
    try:
        return fn(**kw)
    except Exception as exc:
        err = exc
    if "access_token" not in kw and app in _tok() and "401" in str(err):
        return _call(fn, dict(kw, access_token=_tok()[app]))
    allowed = _allowed_params(err)
    drop = [k for k in kw if k in _SAFE_TO_DROP.split() and allowed is not None and k not in allowed]
    if not drop:
        raise err
    return fn(**{k: v for k, v in kw.items() if k not in drop})

def call(apis, app_name, api_name, **kwargs):
    """One API call; tolerates a surplus access_token and adds a forgotten one after a 401."""
    try:
        return _call(_api(apis, app_name, api_name), kwargs, app_name)
    except Exception as exc:
        if "access_token" not in kwargs and ("401" in str(exc) or "token" in str(exc).lower()):
            raise Exception(str(exc) + " [hint: this call had no access_token argument]")
        raise

def login_candidates(profile):
    """Login usernames to try: email, then phone number."""
    out = []
    for key in ("email", "phone_number"):
        val = profile.get(key)
        if val and str(val) not in out:
            out.append(str(val))
    return out

def pick_password(passwords, account_name):
    """Password of the entry whose account_name equals account_name."""
    for entry in passwords:
        if entry.get("account_name") == account_name:
            return entry.get("password")
    raise KeyError("no stored password for account %r; available: %s"
                   % (account_name, [e.get("account_name") for e in passwords]))

def login_all(apis, app_names, login_api, profile, passwords, into=None):
    """Log in to every app in app_names (profile email, then phone number, as username). Returns {app: token};
    `into` (e.g. your `tokens`) is UPDATED in place. Tokens are remembered, so call/get_all/fetch_each/apply_all
    add a forgotten access_token themselves after a 401. Raises if an app cannot be logged into."""
    out = {}
    for app_name in app_names:
        password = pick_password(passwords, app_name)
        tried = []
        for username in login_candidates(profile):
            try:
                res = _api(apis, app_name, login_api)(username=username, password=password)
            except Exception as exc:
                tried.append("%s -> %s" % (username, str(exc)[:80].replace("\n", " ")))
                continue
            out[app_name] = _tok()[app_name] = res["access_token"]
            break
        else:
            raise RuntimeError("login failed for %s; tried: %s" % (app_name, tried))
    if into is not None and into is not out:
        into.update(out)
    return out

def get_all(apis, app_name, api_name, max_pages=200, page_limit=20, **kwargs):
    """Every item of a paginated list API as a flat list. Tolerates a surplus access_token, an API with no
    paging arguments, caller-supplied page_index / page_limit (ignored) and max_pages=None."""
    fn = _api(apis, app_name, api_name)
    kwargs.pop("page_index", None)
    kwargs.pop("page_limit", None)
    if not max_pages:
        max_pages = 200
    items, seen_first = [], None
    use_paging = True
    for page_index in range(max_pages):
        kw = dict(kwargs)
        if use_paging:
            kw.update(page_index=page_index, page_limit=page_limit)
        try:
            page = _call(fn, kw, app_name)
        except Exception as exc:
            allowed = _allowed_params(exc)
            if page_index == 0 and use_paging and allowed is not None and "page_index" not in allowed:
                use_paging = False
                res = _call(fn, dict(kwargs), app_name)
                return res if isinstance(res, list) else [res]
            raise
        if not page:
            break
        if not isinstance(page, list):
            return [page]
        marker = _json.dumps(page[0], sort_keys=True, default=str)
        if marker == seen_first:
            break
        if seen_first is None:
            seen_first = marker
        items.extend(page)
        if len(page) < page_limit:
            break
    return items

def fetch_each(apis, app_name, api_name, id_param, ids, **extra):
    """Call a detail API once per distinct id: {id: result} (a DICT; ids_from/by_field/peek accept it)."""
    fn = _api(apis, app_name, api_name)
    out = {}
    for one in ids:
        if one in out:
            continue
        out[one] = _call(fn, dict({id_param: one}, **extra), app_name)
    return out

def ids_from(items):
    """SONG ids (not artist ids: use artist_ids_of) from a list of dicts or a {id: dict} mapping: 'song_id', a
    'song_ids' list, or a 'songs' list. Order kept, duplicates dropped."""
    seen, out = set(), []

    def add(x):
        if x is not None and x not in seen:
            seen.add(x)
            out.append(x)

    for it in _rows(items):
        if not isinstance(it, dict):
            add(it)
            continue
        add(it.get("song_id"))
        for sid in it.get("song_ids") or []:
            add(sid)
        for s in it.get("songs") or []:
            add(s.get("id", s.get("song_id")) if isinstance(s, dict) else s)
    return out

def _norm(value):
    text = str(value).strip().lower()
    digits = _re.sub(r"\D", "", text)
    if "@" not in text and len(digits) >= 7 and len(digits) >= len(text) - 6:
        return digits[-10:]
    return text

def by_field(items, field, value):
    """Items whose field equals value exactly (case-insensitive; phones by digits) - not fuzzy search hits."""
    target = _norm(value)
    return [it for it in _rows(items) if it.get(field) is not None and _norm(it[field]) == target]

def parse_dt(text):
    """datetime from an ISO timestamp, '2023-05-18' or 'Thursday, May 18, 2023'; None if unparseable."""
    if isinstance(text, _dt.datetime):
        return text.replace(tzinfo=None)
    s = str(text).strip().replace("Z", "")
    s = _re.sub(r"[+-]\d\d:\d\d$", "", s)
    for fmt in _DATE_FORMATS.split("|"):
        try:
            return _dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None

def phone_now(apis, app_name, api_name):
    """Current datetime from the phone clock API."""
    res = _api(apis, app_name, api_name)()
    day = parse_dt(res["date"])
    clock = str(res.get("time", "")).strip()
    for fmt in ("%I:%M %p", "%H:%M:%S", "%H:%M"):
        try:
            t = _dt.datetime.strptime(clock, fmt).time()
            return _dt.datetime.combine(day.date(), t)
        except ValueError:
            continue
    return day

def period_bounds(now, period, n=1):
    """(start, end) datetimes, both inclusive, covering whole days.
    period: today, yesterday, this_month, last_month, this_year, last_year, last_n_days (n days ending today,
    today counted as day 1). Calendar periods are complete: a month runs from the 1st 00:00:00 to the last
    day 23:59:59."""
    day0 = _dt.datetime.combine(now.date(), _dt.time.min)
    end_of = lambda d: _dt.datetime.combine(d.date(), _dt.time(23, 59, 59, 999999))
    if period == "today":
        return day0, end_of(day0)
    if period == "yesterday":
        y = day0 - _dt.timedelta(days=1)
        return y, end_of(y)
    if period == "last_n_days":
        return day0 - _dt.timedelta(days=n - 1), end_of(day0)
    if period == "this_month":
        start = day0.replace(day=1)
        nxt = (start + _dt.timedelta(days=32)).replace(day=1)
        return start, end_of(nxt - _dt.timedelta(days=1))
    if period == "last_month":
        last_day = day0.replace(day=1) - _dt.timedelta(days=1)
        return last_day.replace(day=1), end_of(last_day)
    if period == "this_year":
        return _dt.datetime(now.year, 1, 1), _dt.datetime(now.year, 12, 31, 23, 59, 59, 999999)
    if period == "last_year":
        return _dt.datetime(now.year - 1, 1, 1), _dt.datetime(now.year - 1, 12, 31, 23, 59, 59, 999999)
    raise ValueError("unknown period %r" % (period,))

def in_period(timestamp, start, end):
    """True if the timestamp (string or datetime) lies within [start, end]."""
    dt = parse_dt(timestamp)
    return dt is not None and start <= dt <= end

def money_after(text, label_pattern):
    """Floats that directly follow a label (regex) in text, e.g. a 'Total' line: a LIST, one per match."""
    pat = "(?:" + label_pattern + r")[^0-9\-\n]*?\$?\s*(-?[\d,]+(?:\.\d+)?)"
    out = []
    for m in _re.finditer(pat, text, flags=_re.I):
        out.append(float(m.group(m.lastindex).replace(",", "")))
    return out

def apply_all(apis, app_name, api_name, kwargs_list):
    """Call an API once per kwargs dict, never stopping on a failure. Returns (done, failed): lists of
    (kwargs, result) / (kwargs, error text); prints only a summary - do not print the lists. Print and check the
    target list first, call this once, and if anything failed fix the cause and redo only those."""
    fn = _api(apis, app_name, api_name)
    done, failed = [], []
    kwargs_list = list(kwargs_list)
    if not kwargs_list:
        print("apply_all: EMPTY target list - nothing changed. A wrong key or filter usually made it empty: print one raw item and fix it before complete_task.")
    for kw in kwargs_list:
        try:
            done.append((kw, _call(fn, dict(kw), app_name)))
        except Exception as exc:
            failed.append((kw, str(exc)[:300]))
    print("apply_all: %d ok, %d failed" % (len(done), len(failed)))
    if failed:
        for msg in list(dict.fromkeys(m for _, m in failed))[:3]:
            print("  error: " + msg.replace("\n", " "))
        print("  first failed args: %s" % [{k: v for k, v in kw.items() if "token" not in k} for kw, _ in failed[:3]])
        if any("token" not in kw and "401" in m for kw, m in failed):
            print("  HINT: a 401 with no access_token in the dict - add access_token=tokens['<app>'] to every dict.")
        print("  WARNING: %d change(s) did NOT happen. Fix the cause and redo them before complete_task." % len(failed))
    return done, failed

def need_nonempty(items, what="items"):
    """items, but raises if empty/None - use before a change so a failed lookup stops the step."""
    if not items:
        raise LookupError("nothing found for %s - print the candidates and re-check the filter/spelling" % what)
    return items

def contacts_matching(contacts, first_name=None, last_name=None, relationship=None):
    """Contacts matching first_name / last_name exactly and/or one entry of 'relationships' (no 'name' field)."""
    out = []
    for c in contacts:
        if first_name and str(c.get("first_name") or "").lower() != first_name.lower():
            continue
        if last_name and str(c.get("last_name") or "").lower() != last_name.lower():
            continue
        if relationship and relationship.lower() not in [str(r).lower() for r in (c.get("relationships") or [])]:
            continue
        out.append(c)
    return out

def queue_split(queue):
    """(before, current, after) of a music queue (entries with 'position', is_current / is_playing): already
    played, now playing or None, still to come. Pick the part(s) the task wording means."""
    ordered = sorted(queue, key=lambda e: e.get("position", 0))
    for i, e in enumerate(ordered):
        if e.get("is_current") or e.get("is_playing"):
            return ordered[:i], e, ordered[i + 1:]
    return [], None, ordered

def replace_line(text, needle, old, new):
    """text with `old`->`new` on the FIRST line containing `needle` (case-insensitive) and `old`; raises if none."""
    lines, done = text.split("\n"), False
    for i, ln in enumerate(lines):
        if not done and needle.lower() in ln.lower() and old in ln:
            lines[i] = ln.replace(old, new, 1)
            done = True
    if not done:
        raise LookupError("no line containing %r and %r" % (needle, old))
    return "\n".join(lines)

def artist_ids_of(items):
    """Distinct artist ids from items (list or {id: item} dict) that have an 'artists' list of {id, name}."""
    out = []
    for it in _rows(items):
        for a in (it.get("artists") or []) if isinstance(it, dict) else []:
            x = a.get("id", a.get("artist_id")) if isinstance(a, dict) else a
            if x is not None and x not in out:
                out.append(x)
    return out

def peek(items, n=2):
    """Print size, keys and the first n items; use after building any id set / filtered list (0 or everything
    usually means a wrong key or filter). Returns items."""
    items = _rows(items)
    print("size:", len(items))
    if items and isinstance(items[0], dict):
        print("keys:", sorted(items[0]))
    for it in items[:n]:
        print(" ", str(it)[:200])
    return items

def tx_with(txs, my_email, emails=None):
    """Venmo transactions between me and another person, each as dict(tx, direction='sent'|'received',
    other=<their email>). Raw items have NO direction field. emails: keep only those people (None = everyone)."""
    out = []
    for t in _rows(txs):
        snd, rcv = (t.get("sender") or {}).get("email"), (t.get("receiver") or {}).get("email")
        if my_email not in (snd, rcv):
            continue
        other = rcv if snd == my_email else snd
        if emails is None or other in emails:
            out.append(dict(t, direction="sent" if snd == my_email else "received", other=other))
    return out

def csv_text(header, rows):
    """CSV text, one line per row (header first), a field is quoted only if it holds a comma, quote or newline.
    Join multiple artists/values yourself (e.g. '|'.join(...)) before passing the row."""
    q = lambda v: '"%s"' % str(v).replace('"', '""') if _re.search(r'[,"\n]', str(v)) else str(v)
    return "\n".join(",".join(q(v) for v in r) for r in [header] + [list(r) for r in rows])

def songs_of_artist(apis, app_name, search_api, artist_id, **extra):
    """Songs whose `artists` list contains artist_id: search_api(artist_id=...) via get_all, re-checked on artists[].id
    (a text query by artist NAME is fuzzy and returns other artists' songs)."""
    songs = get_all(apis, app_name, search_api, artist_id=artist_id, **extra)
    return [s for s in songs if artist_id in artist_ids_of([s])]

def play_from(apis, app_name, collection_param, collection_id, song_id, access_token, play_api, queue_api):
    """Play ONE song as part of an album/playlist: start the collection (collection_param='album_id' or
    'playlist_id'), find the song's position in the queue, then play that queue_position. Returns the queue entry."""
    play = _api(apis, app_name, play_api)
    play(**{"access_token": access_token, collection_param: collection_id})
    queue = get_all(apis, app_name, queue_api, access_token=access_token)
    hits = [e for e in queue if e.get("song_id", e.get("id")) == song_id]
    if not hits:
        raise LookupError("song %s not in the queue after starting %s=%s; queue song ids: %s"
                          % (song_id, collection_param, collection_id, [e.get("song_id") for e in queue][:30]))
    play(access_token=access_token, queue_position=hits[-1]["position"])
    return hits[-1]

def pay_any_funding(apis, app_name, pay_api, cards_api, access_token, **kwargs):
    """Make ONE payment without ever topping up: try the balance, then each saved card in turn (an expired card or
    one without enough money is skipped). kwargs go to pay_api (receiver, amount, description...). Returns (result,
    card_id or None); raises with every failure if none worked."""
    pay, errs = _api(apis, app_name, pay_api), []
    try:
        return pay(access_token=access_token, **kwargs), None
    except Exception as exc:
        errs.append("balance: " + str(exc)[:120].replace("\n", " "))
    for card in get_all(apis, app_name, cards_api, access_token=access_token):
        try:
            return pay(access_token=access_token, payment_card_id=card["payment_card_id"], **kwargs), card["payment_card_id"]
        except Exception as exc:
            errs.append("card %s: %s" % (card.get("payment_card_id"), str(exc)[:120].replace("\n", " ")))
    raise RuntimeError("no funding source worked: " + " | ".join(errs))
