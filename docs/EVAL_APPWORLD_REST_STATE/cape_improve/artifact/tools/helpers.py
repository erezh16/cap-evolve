"""Helper functions available in the AppWorld REPL before step 1."""
import re
import datetime as _dt

def _rel_synonyms():
    pa, sb = {"parent", "mother", "father"}, {"sibling", "brother", "sister"}
    return {"parent": pa, "parents": pa, "mother": {"mother", "parent"}, "father": {"father", "parent"},
            "sibling": sb, "siblings": sb, "brother": {"brother", "sibling"}, "sister": {"sister", "sibling"},
            "roommates": {"roommate"}, "friends": {"friend"}, "coworkers": {"coworker"}}

def _tokens(_store={}):
    return _store

def _call_drop(fn, args):
    """Call fn(**args); drop parameters the API rejects as unexpected. Returns (result, dropped_names)."""
    args = dict(args)
    dropped = []
    for _ in range(10):
        try:
            return fn(**args), dropped
        except Exception as e:
            m = re.search(r"Unexpected parameter '(\w+)'", str(e))
            if m and m.group(1) in args:
                dropped.append(m.group(1))
                args.pop(m.group(1))
                continue
            raise
    return fn(**args), dropped

def login_app(apis, supervisor_app, app_name, username, alt_username=None, **_ignored):
    """Log in to app_name and remember the token for call_api/fetch_all (they then add access_token automatically). supervisor_app = the supervisor app's name, username = the supervisor email (phone app: the supervisor phone number). Returns the access token string."""
    passwords = getattr(apis, supervisor_app).show_account_passwords()
    pw = [p["password"] for p in passwords if p["account_name"] == app_name][0]
    try:
        res = getattr(apis, app_name).login(username=username, password=pw)
    except Exception as e:
        if alt_username and "credential" in str(e).lower():
            res = getattr(apis, app_name).login(username=alt_username, password=pw)
        else:
            raise
    token = res["access_token"]
    _tokens()[app_name] = token
    return token

def call_api(apis, app_name, api_name, **kwargs):
    """Call apis.<app_name>.<api_name>(**kwargs). Drops kwargs whose value is None, adds the token saved by login_app, and drops any parameter the API rejects (a WARNING is printed: an invented parameter such as privacy= is NOT sent). If a list API returns 20+ rows (a full page) all pages are fetched automatically. Real errors are re-raised."""
    fn = getattr(getattr(apis, app_name), api_name)
    args = {k: v for k, v in kwargs.items() if v is not None}
    if "access_token" not in args and app_name in _tokens():
        args["access_token"] = _tokens()[app_name]
    auto = "page_index" not in args and "page_limit" not in args
    if auto:
        args["page_limit"] = 20
    res, dropped = _call_drop(fn, args)
    for d in dropped:
        if d != "page_limit":
            print("WARNING: %s.%s ignores parameter %r (it was NOT sent)" % (app_name, api_name, d))
    if auto and "page_limit" not in dropped and isinstance(res, list) and len(res) >= 20:
        args.pop("page_limit")
        args.pop("access_token", None)
        return fetch_all(apis, app_name, api_name, **args)
    return res

def fetch_all(apis, app_name, api_name, page_limit=20, max_pages=None, **kwargs):
    """Return the concatenated list of ALL pages of a paginated list API (page_limit=20, loops page_index until an empty page). Extra kwargs (e.g. access_token, query) pass through. Never pass page_index/max_pages yourself. If the API has no pagination (it rejects page_index), it is called once and its result returned as is (a list or a dict)."""
    kwargs.pop("page_index", None)
    fn = getattr(getattr(apis, app_name), api_name)
    base = {k: v for k, v in kwargs.items() if v is not None}
    if "access_token" not in base and app_name in _tokens():
        base["access_token"] = _tokens()[app_name]
    limit = 500
    out = []
    prev = None
    for page_index in range(limit):
        args = dict(base)
        args["page_index"] = page_index
        args["page_limit"] = page_limit
        page, dropped = _call_drop(fn, args)
        if "page_index" in dropped:
            return page
        if not page:
            break
        if isinstance(page, dict):
            out.append(page)
            break
        if prev is not None and page == prev:
            break
        prev = page
        out.extend(page)
    return out

def finish_task(apis, supervisor_app, task_text, answer=None):
    """Call complete_task correctly. task_text = the EXACT task sentence(s) you were given. If the task is a QUESTION (starts with how many / how much / what / which / who / when / list ..., or contains '?') the answer is passed; otherwise (an action such as follow, like, send, create, move, play, delete, remove) the answer is DROPPED and complete_task() is called with no answer, because action tasks are graded on 'no answer'."""
    text = str(task_text).strip()
    sentences = [x.strip().lower() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    starts = ("how ", "what", "which ", "who ", "whom ", "when ", "where ", "list ", "tell me",
              "give me", "return ", "report ", "find out", "calculate", "count ", "name ")
    is_q = "?" in text or any(x.startswith(starts) for x in sentences)
    is_q = is_q or bool(re.search(r"\b(how many|how much|how long)\b", text.lower()))
    fn = getattr(apis, supervisor_app).complete_task
    if is_q and answer is not None:
        print("finish_task: question task -> answer=%r" % (answer,))
        return fn(answer=answer)
    if answer is not None:
        print("finish_task: ACTION task -> answer %r dropped, complete_task() with no answer" % (answer,))
    return fn()

def phone_today(apis, app_name):
    """Return the app's current date as datetime.date, parsed from the phone clock API (pass the phone app name as app_name). Use this instead of datetime.now()."""
    info = getattr(apis, app_name).get_current_date_and_time()
    text = (info.get("date") or info.get("datetime")) if isinstance(info, dict) else str(info)
    return parse_date(text)

def parse_date(text):
    """Parse 'Thursday, May 18, 2023', '2023-05-18', or '2023-05-18T10:00:00' into a datetime.date."""
    if isinstance(text, dict):
        text = text.get("date") or text.get("datetime")
    if isinstance(text, (_dt.date, _dt.datetime)):
        return text if not isinstance(text, _dt.datetime) else text.date()
    text = str(text).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return _dt.date(int(text[0:4]), int(text[5:7]), int(text[8:10]))
    for fmt in ("%A, %B %d, %Y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y"):
        try:
            return _dt.datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError("cannot parse date: %r" % (text,))

def song_ids_of(obj):
    """Return the list of song ids inside an album/playlist/library entry or song list item. Handles shapes: {'song_ids': [...]}, {'songs': [{'id' or 'song_id': ..}]}, {'song_id': ..}."""
    if obj is None:
        return []
    if isinstance(obj, list):
        ids = []
        for o in obj:
            ids.extend(song_ids_of(o))
        return ids
    if "song_ids" in obj and obj["song_ids"] is not None:
        return list(obj["song_ids"])
    if "songs" in obj and obj["songs"] is not None:
        return [s.get("song_id", s.get("id")) if isinstance(s, dict) else s for s in obj["songs"]]
    if "song_id" in obj:
        return [obj["song_id"]]
    return []

def contacts_with_relation(contacts, relation_words):
    """Filter phone contacts (dicts with a 'relationships' list) by relation words such as ['parents', 'siblings', 'roommate']. Expands synonyms (parents -> parent/mother/father; siblings -> sibling/brother/sister). Returns the matching contact dicts."""
    wanted = set()
    for w in relation_words:
        wanted |= _rel_synonyms().get(str(w).strip().lower(), {str(w).strip().lower()})
    return [c for c in contacts if {str(r).lower() for r in (c.get("relationships") or [])} & wanted]

def find_amount(text, label="Total Amount"):
    """Return the float after '<label> => $' (or '<label>: $') in a bill/receipt text, else None. Takes the LAST match so a grand total wins over line items."""
    pat = re.escape(label) + r"\s*(?:=>|:|-)?\s*\$?\s*([0-9][0-9,]*\.?[0-9]*)"
    hits = re.findall(pat, text, flags=re.I)
    if not hits:
        return None
    return float(hits[-1].replace(",", ""))

def norm_text(s):
    """Lowercase and collapse non-alphanumerics to single spaces (for matching labels/titles)."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(s).lower()).split())

def artist_ids_of(obj):
    """Return artist ids from a song/album/library entry or a list of them. Handles 'artists': [{'id'|'artist_id': ..}], 'artist_ids': [...], and 'artist_id'."""
    if obj is None:
        return []
    if isinstance(obj, list):
        ids = []
        for o in obj:
            ids.extend(artist_ids_of(o))
        return ids
    ids = []
    for a in obj.get("artists") or []:
        if isinstance(a, dict):
            v = a.get("id", a.get("artist_id"))
            if v is not None:
                ids.append(v)
        else:
            ids.append(a)
    ids.extend(obj.get("artist_ids") or [])
    if obj.get("artist_id") is not None:
        ids.append(obj["artist_id"])
    return ids

def songs_of_artist(apis, app_name, artist_name, artist_search_api, song_search_api):
    """All songs by one artist (exact name match). Looks the artist up with artist_search_api, then lists songs with song_search_api(artist_id=...) and keeps only songs that really list that artist. A text query is NOT enough: it returns the whole catalog. Rows include play_count, rating, duration. Example: songs_of_artist(apis, 'spotify', 'Name Here', 'search_artists', 'search_songs')"""
    want = norm_text(artist_name)
    found = fetch_all(apis, app_name, artist_search_api, query=artist_name)
    exact = [a for a in found if norm_text(a.get("name", "")) == want]
    if not exact:
        raise ValueError("no artist named %r; candidates: %r" % (artist_name, [a.get("name") for a in found][:10]))
    aid = exact[0].get("artist_id", exact[0].get("id"))
    songs = fetch_all(apis, app_name, song_search_api, artist_id=aid)
    return [s for s in songs if aid in artist_ids_of(s)]

def playlist_minutes(apis, app_name, show_song_api, song_ids):
    """Total length in MINUTES (float) of the given song ids. Song 'duration' is in SECONDS (there is no duration_ms). Playlist-library entries only carry song_ids, so each song is looked up with show_song_api (a no-token song detail API)."""
    total = 0
    for sid in song_ids:
        total += call_api(apis, app_name, show_song_api, song_id=sid).get("duration") or 0
    return total / 60.0

def queue_played_so_far(queue):
    """From a music-player queue (list of entries with 'position' and 'is_current'/'is_playing'), return the entries played so far INCLUDING the current one (position <= current position)."""
    cur = [e["position"] for e in queue if e.get("is_current") or e.get("is_playing")]
    if not cur:
        raise ValueError("no current entry in queue; print the queue entries and decide")
    return [e for e in queue if e.get("position") <= cur[0]]

def pick_extreme_song(apis, app_name, show_song_api, song_ids, mode):
    """Song dict (keys id, song_id, title, play_count) with the max ('max') or min ('min') play_count among exactly song_ids ("most/least listened to/played"). play_count exists only in show_song_api details."""
    rows = [r for r in song_details(apis, app_name, show_song_api, song_ids) if r.get("play_count") is not None]
    return (max if mode == "max" else min)(rows, key=lambda r: r["play_count"])

def play_in_collection(apis, app_name, play_api, queue_api, song_id, **collection):
    """Play one song INSIDE its album/playlist: first play the collection (pass album_id=.. or playlist_id=..), then jump to the song's queue position. Playing a bare song_id queues that single song and does NOT count as playing it from the collection. Use for ANY task that plays a song 'from/of the X album/playlist' (including most/least listened)."""
    call_api(apis, app_name, play_api, **collection)
    queue = call_api(apis, app_name, queue_api)
    cur = [e["position"] for e in queue if e.get("is_current")]
    start = cur[0] if cur else 0
    pos = [e["position"] for e in queue if e.get("song_id") == song_id and e["position"] >= start]
    if not pos:
        raise ValueError("song %r not in queue after playing the collection" % (song_id,))
    return call_api(apis, app_name, play_api, queue_position=pos[0])

def filter_txns(txns, emails=None, dates=None, role="either"):
    """Filter transaction dicts (sender/receiver {name,email}, created_at). emails = set of people emails; role = 'sender' | 'receiver' | 'either' says where the email must be; dates = set of datetime.date (or None for all days)."""
    out = []
    dates = None if dates is None else {parse_date(d) for d in dates}
    for t in txns:
        if dates is not None and parse_date(t["created_at"]) not in dates:
            continue
        if emails is not None:
            s = (t.get("sender") or {}).get("email")
            r = (t.get("receiver") or {}).get("email")
            ok = {"sender": s in emails, "receiver": r in emails}.get(role, s in emails or r in emails)
            if not ok:
                continue
        out.append(t)
    return out

def send_with_any_card(apis, app_name, send_api, cards_api, **kwargs):
    """Send money without topping up the balance: try send_api(**kwargs) as is; if the balance is too low or the card is refused, retry with each payment card (payment_card_id=..) from cards_api until one works. Other errors are re-raised. Never add money to the balance."""
    try:
        return call_api(apis, app_name, send_api, **kwargs)
    except Exception as e:
        if "balance" not in str(e).lower():
            raise
    last = None
    for card in fetch_all(apis, app_name, cards_api):
        try:
            return call_api(apis, app_name, send_api, payment_card_id=card.get("payment_card_id", card.get("id")), **kwargs)
        except Exception as e:
            low = str(e).lower()
            if "expired" in low or "does not have" in low or "insufficient" in low or "balance" in low:
                last = e
                continue
            raise
    raise last if last else ValueError("no usable payment card")

def shift_month(day, n):
    """Return (year, month) of datetime.date day shifted by n months (n=-1 is last month)."""
    idx = day.year * 12 + (day.month - 1) + n
    return idx // 12, idx % 12 + 1

def pick_month_file(paths, year, month):
    """From file paths named like .../YYYY-MM.txt (or YYYY_MM), return the ones for that year and month. Use the file NAME for the period; never take paths[0]."""
    ms = [(p, re.search(r"(\d{4})[-_](\d{2})[^/]*$", p)) for p in paths]
    return [p for p, m in ms if m and (int(m.group(1)), int(m.group(2))) == (year, month)]

def year_of(ts):
    """Year (int) of any ISO date/datetime string such as '2020-03-08T02:26:07'."""
    return parse_date(ts).year

def year_matches(ts, rule, year):
    """True if the year of ts satisfies rule vs year. rule: 'before' | 'after' (both STRICT) | 'in_or_before' | 'in_or_after' | 'in'."""
    y = year_of(ts)
    table = {"before": y < year, "after": y > year, "in_or_before": y <= year, "in_or_after": y >= year, "in": y == year}
    if rule not in table:
        raise ValueError("rule must be one of %r" % (sorted(table),))
    return table[rule]

def song_details(apis, app_name, show_song_api, ids):
    """LIST of full song detail dicts (keys song_id AND id, title, release_date, genre, play_count, duration...) via show_song_api (no-token song detail API), in the order of ids. Use `for d in details`, `details[0]`, `details.get(song_id)`. List rows (library, liked, queue, playlist) lack release_date/genre/play_count; call this for EVERY id before filtering by them. Store the result in a NEW variable name, never `song_details = song_details(...)`."""
    class _Rows(list):
        def get(self, key, default=None):
            return next((r for r in self if key in (r.get("song_id"), r.get("id"))), default)
        def values(self):
            return list(self)
    out = _Rows()
    for i in dict.fromkeys(ids):
        d = dict(call_api(apis, app_name, show_song_api, song_id=i))
        d.setdefault("id", i)
        out.append(d)
    return out

def library_song_ids(apis, app_name, song_lib_api=None, album_lib_api=None, playlist_lib_api=None):
    """De-duplicated song ids over ONLY the libraries you pass (None = skip). Task says 'song library' -> pass only song_lib_api; 'album library' -> only album_lib_api; 'playlist library' -> only playlist_lib_api; pass all three only for 'across my libraries'."""
    ids = []
    for api in (song_lib_api, album_lib_api, playlist_lib_api):
        if api:
            ids.extend(song_ids_of(fetch_all(apis, app_name, api)))
    return list(dict.fromkeys(ids))

def review_id_of(rev):
    """Id of a review dict: the first key ending in 'review_id' (e.g. song_review_id), else 'id'."""
    for k in rev:
        if k.endswith("review_id"):
            return rev[k]
    return rev["id"]

def set_my_rating(apis, app_name, reviews_api, review_api, update_api, song_id, email, rating, only="any"):
    """Make MY rating of a song equal `rating`: creates the review (review_api) or updates the existing one (update_api). only='raise' changes it only if the current rating is lower, 'lower' only if higher, 'any' if different. The song's own show_song rating is the community average, never use it. Returns 'created' | 'updated' | 'kept'."""
    revs = fetch_all(apis, app_name, reviews_api, song_id=song_id, user_email=email)
    rev = revs[0] if revs else None
    if rev is None:
        call_api(apis, app_name, review_api, song_id=song_id, rating=rating)
        return "created"
    cur = rev.get("rating")
    if cur == rating or (only == "raise" and cur > rating) or (only == "lower" and cur < rating):
        return "kept"
    call_api(apis, app_name, update_api, review_id=review_id_of(rev), rating=rating)
    return "updated"

def csv_text(header, rows):
    """Plain CSV text: header list + rows (lists). A field is quoted ONLY if it contains a comma, quote or newline (never quote every field); no trailing newline. Do not import csv/io/os."""
    def cell(v):
        v = "" if v is None else str(v)
        return '"' + v.replace('"', '""') + '"' if any(c in v for c in ',"\n') else v
    return "\n".join([",".join(cell(h) for h in header)] + [",".join(cell(c) for c in r) for r in rows])

def library_song_rows(apis, app_name, song_lib_api, album_lib_api, playlist_lib_api, show_song_api, sep="|"):
    """Unique [title, 'Artist1|Artist2'] rows for every song in the song library, album library and all playlists (artist names from the song detail's 'artists' list)."""
    ids = library_song_ids(apis, app_name, song_lib_api, album_lib_api, playlist_lib_api)
    return [[s["title"], sep.join(a["name"] for a in s["artists"])] for s in song_details(apis, app_name, show_song_api, ids)]

def weekday_name(d):
    """Lowercase weekday name of a datetime.date, e.g. 'wednesday'."""
    return ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][d.weekday()]

def day_value(text, day_name, key):
    """Number after '<key>:' inside the block of a note that starts with 'day: <day_name>' (weekly plans). Never regex the first number of the whole note."""
    for b in re.split(r"(?im)^\s*day\s*:\s*", text)[1:]:
        if b.strip().lower().startswith(day_name.lower()):
            m = re.search(r"(?im)^\s*" + re.escape(key) + r"\s*:\s*([0-9.]+)", b)
            if m:
                return float(m.group(1))
    raise ValueError("no %r for %r; print the note and read it" % (key, day_name))

def relation_emails(apis, app_name, search_contacts_api, words):
    """Set of emails of phone contacts with the relation words, e.g. ['friends'], ['siblings'], ['coworkers']. 'My friends/coworkers/...' always means phone contacts, never venmo friends."""
    cs = fetch_all(apis, app_name, search_contacts_api)
    return {c["email"] for c in contacts_with_relation(cs, words) if c.get("email")}

def txns_between(txns, my_email, direction, others=None, dates=None, desc=None):
    """Filter venmo transactions. direction='received' = I am the receiver (others are senders); 'sent' = I am the sender. others = set of emails (or None), dates = set of datetime.date (or None), desc = text that must appear in the description (or None)."""
    out = []
    dates = None if dates is None else {parse_date(d) for d in dates}
    for t in txns:
        s = (t.get("sender") or {}).get("email")
        r = (t.get("receiver") or {}).get("email")
        me, other = (r, s) if direction == "received" else (s, r)
        if me != my_email or (others is not None and other not in others):
            continue
        if dates is not None and parse_date(t["created_at"]) not in dates:
            continue
        if desc and norm_text(desc) not in norm_text(t.get("description", "")):
            continue
        out.append(t)
    return out

def note_blocks(text):
    """Parse a note of entries like 'Title' followed by ' - key: value' lines into a de-duplicated list of dicts {'title':.., key:value..} (keys lowercase). Filter with e.g. [b['title'] for b in note_blocks(t) if 'nolan' in b.get('director','').lower()]."""
    out, seen = [], set()
    for ln in text.splitlines():
        m = re.match(r"^\s*[-*]\s*([\w ]+?)\s*:\s*(.*)$", ln)
        if m and out:
            out[-1][m.group(1).lower()] = m.group(2).strip()
        elif ln.strip() and not ln.lstrip().startswith(("#", "-", "*")):
            out.append({"title": ln.strip(), "dup": ln.strip() in seen})
            seen.add(ln.strip())
    return [b for b in out if not b.pop("dup")]

def note_shares(text):
    """{name: amount} from lines like '- Name => $33' or '- Name: $33' of a share note. Empty dict = wrong note: look at the other notes, never finish."""
    return {m[0].strip(): float(m[1]) for m in re.findall(r"^\s*[-*]\s*([A-Za-z][\w .]*?)\s*(?:=>|:|-)\s*\$?([0-9]+\.?[0-9]*)\s*$", text, flags=re.M)}

def has_account(rows, email):
    """True only if a search_users result list `rows` has a row whose email equals `email` (case-insensitive). The search is fuzzy and never empty, so 'rows is non-empty' proves nothing."""
    return any(str(r.get("email", "")).lower() == str(email).lower() for r in rows)
