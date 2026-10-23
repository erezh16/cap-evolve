"""Generic helpers available in the REPL. All take `apis` plus app / API names as arguments.

call_api(apis, app, api, **kw)                      call any API by name
paginate(apis, app, api, **kw)                      ALL items of a paged list API (page_limit=20, stops on empty page)
app_login(apis, app, login_api, usernames, passwords)  -> access_token (tries each username, e.g. [email, phone])
app_today(apis, app, api)                           -> datetime.date from the phone-style date API (the real "now")
shift_days(d, n) / iso(d) / date_part(ts) / days_since(ts, today) / in_window(ts, start, end)
contacts_by(apis, app, api, token, wanted)          contacts whose `relationships` list matches wanted labels
label_match(relationships, wanted)                  case/hyphen/plural-insensitive + parent/sibling synonyms
search_exact(apis, app, api, query, value, field)   fuzzy search, keep only EXACT field matches
try_each(apis, app, api, key, options, **kw)        call with each option (e.g. payment_card_id) until one works
unexpired_card_ids(cards, today)                    ids of cards not past expiry
song_ids_in(items) / fetch_details(apis, app, api, ids, id_key)   collect song ids / get per-id detail dicts
bulk_call(apis, app, api, items, key, **kw)         call once per item, report ok / errors (nothing hidden)
money_lines(text) / money_after(text, label)        parse "$" amounts from note / file / message text
peek(x, n)                                          print type, length, keys and first n items
"""
import re
import json
import datetime


def call_api(apis, app, api, **kw):
    return getattr(getattr(apis, app), api)(**kw)


def paginate(apis, app, api, max_pages=200, **kw):
    """Return every item of a paged list API. Pass access_token etc. as keywords."""
    kw.pop("page_index", None)
    kw.setdefault("page_limit", 20)
    out, prev = [], None
    for i in range(max_pages):
        page = call_api(apis, app, api, page_index=i, **kw)
        if not isinstance(page, list):
            raise TypeError("paginate: %s returned %s, not a list: %s" % (api, type(page).__name__, str(page)[:200]))
        if not page or page == prev:
            break
        out.extend(page)
        prev = page
    return out


def app_login(apis, app, login_api, usernames, passwords):
    """passwords = the supervisor password list. usernames = one or several candidates."""
    if isinstance(usernames, str):
        usernames = [usernames]
    found = [p.get("password") for p in passwords if p.get("account_name") == app]
    if not found:
        raise ValueError("no password entry for app %r; accounts: %s" % (app, [p.get("account_name") for p in passwords]))
    errors = []
    for u in usernames:
        try:
            res = call_api(apis, app, login_api, username=u, password=found[0])
            return res["access_token"]
        except Exception as e:  # try the next username candidate, report all at the end
            errors.append("%s: %s" % (u, str(e)[-120:]))
    raise RuntimeError("login failed for %s: %s" % (app, errors))


def app_today(apis, app, api):
    res = call_api(apis, app, api)
    return datetime.datetime.strptime(res["date"].strip(), "%A, %B %d, %Y").date()


def shift_days(d, n):
    return d + datetime.timedelta(days=n)


def iso(d):
    return d.strftime("%Y-%m-%d")


def date_part(ts):
    return str(ts)[:10]


def days_since(ts, today):
    d = datetime.datetime.strptime(date_part(ts), "%Y-%m-%d").date()
    return (today - d).days


def in_window(ts, start, end):
    """Inclusive date-window test; start/end are 'YYYY-MM-DD' strings or dates (None = open)."""
    s, e = (iso(start) if hasattr(start, "year") else start), (iso(end) if hasattr(end, "year") else end)
    d = date_part(ts)
    return (s is None or d >= s) and (e is None or d <= e)


def _canon(s):
    s = re.sub(r"[^a-z0-9]", "", str(s).lower())
    return s[:-1] if s.endswith("s") and len(s) > 3 else s


def label_match(relationships, wanted):
    """True if any label in `relationships` matches any wanted label (parent/sibling synonyms included)."""
    groups = [
        {"parent", "mother", "father", "mom", "dad", "stepmother", "stepfather"},
        {"sibling", "brother", "sister", "stepbrother", "stepsister"},
        {"coworker", "colleague"},
        {"child", "son", "daughter"},
        {"spouse", "wife", "husband", "partner"},
    ]
    if isinstance(wanted, str):
        wanted = [wanted]
    if isinstance(relationships, str):
        relationships = [relationships]
    have = {_canon(r) for r in (relationships or [])}
    for w in wanted:
        cw = _canon(w)
        allowed = {cw}
        for g in groups:
            if cw in g:
                allowed |= g
        if have & allowed:
            return True
    return False


def contacts_by(apis, app, api, token, wanted, **kw):
    """All contacts (every page, de-duplicated) whose relationships match `wanted` (a label or list of labels)."""
    allc = paginate(apis, app, api, access_token=token, **kw)
    seen, out = set(), []
    for c in allc:
        key = c.get("contact_id", c.get("email"))
        if key in seen:
            continue
        seen.add(key)
        if label_match(c.get("relationships"), wanted):
            out.append(c)
    if not out:
        print("contacts_by: no match for %s; labels present: %s" % (wanted, sorted({r for c in allc for r in c.get("relationships", [])})))
    return out


def search_exact(apis, app, api, query, value, field="email", **kw):
    """Fuzzy search results are never proof of existence: keep only items whose `field` equals `value`."""
    items = paginate(apis, app, api, query=query, **kw)
    v = str(value).strip().lower()
    return [i for i in items if str(i.get(field, "")).strip().lower() == v]


def try_each(apis, app, api, key, options, **kw):
    """Call api with kw plus {key: option} for each option (None = leave out) until one succeeds."""
    errors = []
    for o in options:
        k = dict(kw)
        if o is not None:
            k[key] = o
        try:
            return {"result": call_api(apis, app, api, **k), "option": o}
        except Exception as e:  # keep trying; every failure is reported if none works
            errors.append((o, str(e)[-160:]))
    raise RuntimeError("try_each: all %d options failed: %s" % (len(errors), errors))


def unexpired_card_ids(cards, today):
    ok = []
    for c in cards:
        y, m = int(c.get("expiry_year", 0)), int(c.get("expiry_month", 0))
        if (y, m) >= (today.year, today.month):
            ok.append(c["payment_card_id"])
    return ok


def song_ids_in(items):
    """Song ids found in library / queue / detail items: song_id, song_ids, or songs[{id|song_id}]. Unique, ordered."""
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get("song_id") is not None:
            out.append(it["song_id"])
        out.extend(it.get("song_ids") or [])
        for s in it.get("songs") or []:
            out.append(s.get("id", s.get("song_id")))
    return list(dict.fromkeys(i for i in out if i is not None))


def fetch_details(apis, app, api, ids, id_key, **kw):
    """{id: detail dict} by calling the per-id detail API once for each id (errors are raised, not hidden)."""
    return {i: call_api(apis, app, api, **{id_key: i}, **kw) for i in ids}


def bulk_call(apis, app, api, items, key, **kw):
    """Call api once per item with {key: item}. Returns [(item, ok, result_or_error)] and prints a summary."""
    res = []
    for it in items:
        try:
            res.append((it, True, call_api(apis, app, api, **{key: it}, **kw)))
        except Exception as e:  # recorded below, never silent
            res.append((it, False, str(e)[-160:]))
    bad = [r for r in res if not r[1]]
    print("bulk_call %s: %d ok, %d failed" % (api, len(res) - len(bad), len(bad)))
    for msg in sorted({b[2] for b in bad}):
        print("  error:", msg, "| items:", [b[0] for b in bad if b[2] == msg][:10])
    return res


def money_lines(text):
    """[(label, amount)] for each line holding a $ amount, e.g. '- Name => $20' -> ('Name', 20.0)."""
    out = []
    for line in str(text).splitlines():
        m = re.findall(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)", line)
        if m:
            label = re.split(r"\s*(?:=>|->|:|\||\s-\s|\$)", line.lstrip("-*# \t"))[0].strip()
            out.append((label, float(m[-1].replace(",", ""))))
    return out


def money_after(text, label):
    """First $ amount after `label` (case-insensitive regex, e.g. 'total amount'); raises if absent."""
    m = re.search(label + r"[^0-9$\n]*\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)", str(text), re.I)
    if not m:
        raise ValueError("money_after: %r not found in text: %s" % (label, str(text)[:300]))
    return float(m.group(1).replace(",", ""))


def peek(x, n=2):
    if isinstance(x, list):
        print("list of %d" % len(x))
        for it in x[:n]:
            print(" ", json.dumps(it, default=str)[:600])
    elif isinstance(x, dict):
        print("dict keys:", list(x.keys()))
        print(" ", json.dumps(x, default=str)[:800])
    else:
        print(type(x).__name__, str(x)[:600])
