"""Generic helpers defined in the REPL before step 1. All take `apis` and app/API names as arguments."""
import re, json, datetime as _dt

def _api(apis, app_name, api_name):
    return api_name if callable(api_name) else getattr(getattr(apis, app_name), api_name)

def _hint(exc):
    msg = str(exc) + (' || HINT: this API needs access_token=<token from login_app for THIS app>' if '401' in str(exc) else '')
    return RuntimeError(msg)

def fetch_all_pages(apis, app_name, api_name, max_pages=200, **kwargs):
    """Call a list API with page_limit=20 and collect ALL rows, stopping only at an EMPTY page (page_index is managed
    here; max_pages=None = no cap). An error dict is raised. An API without paging params is called once."""
    if 'access_token' in kwargs and not kwargs['access_token']:
        raise ValueError('access_token is empty: log in first (login_app)')
    fn = _api(apis, app_name, api_name)
    kwargs = dict(kwargs)
    kwargs.setdefault('page_limit', 20)
    kwargs.pop('page_index', None)
    rows = []
    for page_index in range(10 ** 6 if max_pages is None else max_pages):
        try:
            page = fn(page_index=page_index, **kwargs)
        except Exception as exc:
            if 'nexpected' in str(exc) and 'page_' in str(exc) and page_index == 0:
                kwargs.pop('page_limit', None)
                try:
                    return list(fn(**kwargs))
                except Exception as exc2:
                    raise _hint(exc2)
            raise _hint(exc)
        if isinstance(page, dict):
            raise RuntimeError(str(page.get('message', page)))
        if not page:
            break
        rows.extend(page)
    return rows

def find_password(passwords, account_name):
    """Password of the entry whose account_name matches (None if absent); a plain string is returned as is."""
    if isinstance(passwords, str):
        return passwords
    return next((e.get('password') for e in passwords if e.get('account_name') == account_name), None)

def login_app(apis, app_name, login_api_name, username, passwords, alt_username=None):
    """Log in with the supervisor password list (or one password string); returns the access token STRING
    (tok['access_token'] also works). If rejected, alt_username is tried next."""
    password = find_password(passwords, app_name)
    if password is None:
        raise ValueError('no password entry for ' + str(app_name))
    fn = _api(apis, app_name, login_api_name)
    try:
        token = fn(username=username, password=password)['access_token']
    except Exception:
        if alt_username is None:
            raise
        token = fn(username=alt_username, password=password)['access_token']

    class _Token(str):
        def __getitem__(self, key):
            return str(self) if key in ('access_token', 'token') else str.__getitem__(self, key)

    return _Token(token)

def _cell(v):
    if isinstance(v, (list, tuple, set)):
        return '|'.join(_cell(x) for x in v)
    if isinstance(v, dict):
        return next((str(v[k]) for k in ('name', 'title', 'email', 'id') if k in v), json.dumps(v, sort_keys=True))
    return str(v)

def to_csv(rows, header=None):
    """Plain CSV text, NO quoting; rows are lists or dicts (header default = keys); list cells joined with '|'."""
    rows = list(rows)
    if rows and isinstance(rows[0], dict):
        header = header or list(rows[0].keys())
        rows = [[r[h] for h in header] for r in rows]
    return '\n'.join([','.join(str(h) for h in header)] * bool(header) + [','.join(_cell(v) for v in row) for row in rows])

def find_amounts(text):
    """Return all dollar amounts in text as floats, e.g. 'Total => $1,234.50' -> [1234.5]."""
    return [float(m.replace(',', '')) for m in re.findall(r'\$\s*([0-9][0-9,]*\.?[0-9]*)', text)]

def get_field(row, name):
    """row[name], but a missing key raises a KeyError that lists the real keys (no silent default)."""
    if not isinstance(row, dict) or name not in row:
        raise KeyError('no field ' + repr(name) + '; real keys: ' + str(sorted(row) if isinstance(row, dict) else type(row).__name__))
    return row[name]

def ensure_nonempty(label, rows):
    """Return rows unchanged, but raise if empty/zero (usually a wrong field, filter or parameter): debug before acting."""
    if rows is None or (not isinstance(rows, (int, float)) and len(rows) == 0) or rows == 0:
        raise ValueError(str(label) + ' came back empty/zero: re-check field names, filters, dates and pagination')
    return rows

def sample_keys(rows, n=1):
    """Print the keys and first n rows of a list so the real field names are seen before filtering."""
    rows = list(rows)
    print('count =', len(rows), *[json.dumps(r, default=str)[:600] for r in rows[:n]], 'keys = ' + str(sorted(rows[0]) if rows and isinstance(rows[0], dict) else ''), sep='\n')

def parse_date(value):
    """date from 'YYYY-MM-DD...' / 'YYYY/MM/DD' or a long form like 'Thursday, May 18, 2023' (time ignored)."""
    if isinstance(value, _dt.date):
        return value.date() if isinstance(value, _dt.datetime) else value
    text = str(value).strip()
    m = re.match(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', text)
    if m:
        return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    text = re.sub(r'^[A-Za-z]+day,\s*', '', text)
    for fmt in ('%B %d, %Y', '%b %d, %Y', '%d %B %Y'):
        try:
            return _dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError('cannot parse date: ' + str(value))

def sandbox_today(apis, app_name, api_name):
    """Today's date (date) from the sandbox clock API; handles its long text date format."""
    res = _api(apis, app_name, api_name)()
    return parse_date(res['date'] if isinstance(res, dict) and 'date' in res else res)

def month_range(today, offset=0):
    """(first_day, last_day) of the calendar month that is `offset` months from today (-1 = last month)."""
    idx = today.year * 12 + (today.month - 1) + offset
    return _dt.date(idx // 12, idx % 12 + 1, 1), _dt.date((idx + 1) // 12, (idx + 1) % 12 + 1, 1) - _dt.timedelta(days=1)

def bill_total(text):
    """Amount on the 'Total' line of a bill/receipt text: the last dollar amount on the last line that
    contains the word total (case-insensitive). Raises if there is none, so print the file and read it."""
    found = [find_amounts(ln)[-1] for ln in text.splitlines() if re.search(r'total', ln, re.I) and find_amounts(ln)]
    if not found:
        raise ValueError('no Total line with a dollar amount; print the file text and read it')
    return found[-1]

def contacts_by_relationship(contacts, word):
    """Contacts (fetch_all_pages rows) whose relationships list contains `word`, case-insensitive."""
    return [c for c in contacts if any(word.lower() == str(r).lower() for r in get_field(c, 'relationships'))]

def try_each(apis, app_name, api_name, option_list, param_name=None, **kwargs):
    """Call an API with each option (dict, or plain value with param_name) merged into kwargs; stop at the FIRST call
    that does not raise; returns (option, result)."""
    fn = _api(apis, app_name, api_name)
    errors = []
    for opt in option_list:
        opt = opt if isinstance(opt, dict) else {param_name: opt}
        try:
            return opt, fn(**dict(kwargs, **opt))
        except Exception as exc:
            errors.append(str(exc)[:200])
    raise RuntimeError('all options failed: ' + ' | '.join(errors))

def run_once(label, key, fn, *args, **kwargs):
    """fn(*args, **kwargs) at most once per (label, key); a repeat returns the earlier result (no double side effects)."""
    done = run_once.__dict__.setdefault('done', {})
    k = (str(label), str(key))
    if k in done:
        print('SKIP (already done):', k)
    else:
        done[k] = fn(*args, **kwargs)
    return done[k]

def apply_each(label, items, key_fn, fn):
    """Run fn(item) once per item (keyed by key_fn); errors are raised AFTER the loop. Call again with the SAME label
    after fixing: finished items are skipped."""
    items = list(items)
    if not items:
        raise ValueError('apply_each ' + str(label) + ' got 0 items: the list is wrong (field, filter, dates); debug it, do not complete_task')
    results, errors = [], []
    for item in items:
        try:
            results.append(run_once(label, key_fn(item), fn, item))
        except Exception as exc:
            errors.append((key_fn(item), str(exc)[:200]))
    print('apply_each', label, ': ok', len(results), '/', len(items))
    if errors:
        raise RuntimeError('failed items (fix, then call again with the same label): ' + str(errors))
    return results

def pay_with_fallback_cards(apis, app_name, api_name, cards, today, **kwargs):
    """Call a payment API; if it fails (e.g. balance too low), retry with each NON-expired card's payment_card_id.
    Never tops up a balance. Returns (option_used, result). cards = supervisor card rows, today = sandbox date."""
    options = [{}] + [{'payment_card_id': get_field(c, 'payment_card_id')} for c in cards
                      if (int(get_field(c, 'expiry_year')), int(get_field(c, 'expiry_month'))) >= (today.year, today.month)]
    return try_each(apis, app_name, api_name, options, **kwargs)

def match_contacts(contacts, name, relationship=None):
    """The ONE contact whose full (or first) name equals `name`, optionally with `relationship`; raises on 0 or 2+."""
    pool = contacts_by_relationship(contacts, relationship) if relationship else list(contacts)
    words = str(name).strip().lower().split()
    full = lambda c: (get_field(c, 'first_name') + ' ' + get_field(c, 'last_name')).lower()
    hits = [c for c in pool if full(c) == ' '.join(words)]
    if not hits:
        hits = [c for c in pool if get_field(c, 'first_name').lower() == words[0]
                and (len(words) == 1 or get_field(c, 'last_name').lower() == words[-1])]
    if len(hits) != 1:
        raise ValueError(str(name) + ' matched ' + str(len(hits)) + ' contacts: ' +
                         str([(full(c), c['relationships'], c['email']) for c in hits or pool][:8]))
    return hits[0]

def bill_rows(apis, app_name, list_api, read_api, token, directory='~/bills/', kind=None, year=None):
    """Readable .txt bills under `directory` whose path has /kind/ and whose period starts in `year`; prints and returns
    (path, start, end, amount) rows. .pdf copies are skipped."""
    paths = [p for p in _api(apis, app_name, list_api)(access_token=token, directory_path=directory, entry_type='files',
             recursive=True) if kind is None or '/' + kind.lower() + '/' in p.lower()]
    ensure_nonempty('bill files for ' + str(kind), paths)
    print('skipped (pdf):', [p for p in paths if p.lower().endswith('.pdf')])
    rows = []
    for p in [p for p in paths if not p.lower().endswith('.pdf')]:
        text = _api(apis, app_name, read_api)(access_token=token, file_path=p)['content']
        m = re.search(r'(\d{4}-\d{2}-\d{2})\s*(?:to|-)\s*(\d{4}-\d{2}-\d{2})', text)
        if not m:
            raise ValueError('no "YYYY-MM-DD to YYYY-MM-DD" period in ' + p + '; print its text and read it')
        start, end, amount = parse_date(m.group(1)), parse_date(m.group(2)), bill_total(text)
        if year is None or start.year == year:
            rows.append({'path': p, 'start': start, 'end': end, 'amount': amount})
    print(*[(r['path'], str(r['start']), str(r['end']), r['amount']) for r in rows], sep='\n')
    print('bills:', len(rows), 'sum:', round(sum(r['amount'] for r in rows), 2))
    return rows

def join_path(*parts):
    """Join path parts with exactly one '/' between them (a '//' gets a 422 from the file API)."""
    out = str(parts[0])
    for p in parts[1:]:
        out = out.rstrip('/') + '/' + str(p).lstrip('/')
    return out

def list_paths(apis, app_name, list_api, token, directory, kind='files', recursive=False):
    """Sorted path STRINGS under `directory`: kind='files' or 'directories' (no trailing '/'); direct children unless recursive."""
    ensure_nonempty("kind must be 'files' or 'directories'", [kind] if kind in ('files', 'directories') else [])
    rows = _api(apis, app_name, list_api)(access_token=token, directory_path=directory, entry_type='all', recursive=recursive)
    out = sorted(p.rstrip('/') for p in rows if p.endswith('/') == (kind == 'directories'))
    print(kind, 'in', directory, ':', len(out)); return out

def file_dates(apis, app_name, read_api, token, paths):
    """[{'path','dir','name','created'(datetime),'created_at','date','year','month','day'}] per file (one read each)."""
    out = []
    for p in paths:
        c = _dt.datetime.fromisoformat(str(get_field(_api(apis, app_name, read_api)(
            access_token=token, file_path=p), 'created_at')).rstrip('Z')[:19])
        out.append({'path': p, 'dir': p.rpartition('/')[0], 'name': p.rpartition('/')[2], 'created': c, 'created_at': c.isoformat(),
                    'date': str(c.date()), 'year': c.year, 'month': c.month, 'day': c.day})
    print('files:', len(out), 'years:', sorted({r['year'] for r in out}))
    return out

def move_checked(apis, app_name, move_api, list_api, token, pairs, overwrite=False, mkdir_api=None):
    """Move/rename [(src, dst), ...]: rejects '//', duplicate destinations and an empty plan; mkdir_api (create_directory)
    first creates every destination folder; moves each pair once, re-lists to verify."""
    pairs = [(str(s), str(d)) for s, d in pairs]
    ensure_nonempty('move plan (0 pairs)', pairs)
    dests = [d for _, d in pairs]
    for folder in sorted({d.rpartition('/')[0] for d in dests}) if mkdir_api else []:
        _api(apis, app_name, mkdir_api)(access_token=token, directory_path=folder, recursive=True, allow_if_exists=True)
    if any('//' in d.replace('~/', '', 1) for d in dests) or len(set(dests)) != len(dests):
        raise ValueError('bad plan: double slash or two sources for one destination')
    errors = []
    for s, d in pairs:
        try:
            run_once('move_checked', s + '>' + d, _api(apis, app_name, move_api), access_token=token,
                     source_file_path=s, destination_file_path=d, overwrite=overwrite, retain_dates=True)
        except Exception as exc:
            errors.append((s, d, str(exc)[:160]))
    print('moved', len(pairs) - len(errors), '/', len(pairs))
    if errors:
        raise RuntimeError('failed moves: ' + str(errors[:5]))
    for folder in sorted({d.rpartition('/')[0] for d in dests}):
        have = {p.rpartition('/')[2] for p in _api(apis, app_name, list_api)(
            access_token=token, directory_path=folder, entry_type='files', recursive=False)}
        miss = [d for d in dests if d.rpartition('/')[0] == folder and d.rpartition('/')[2] not in have]
        if miss:
            raise RuntimeError('missing after move in ' + folder + ': ' + str(miss[:5]))
    return pairs

def archive_dirs(apis, app_name, compress_api, delete_api, list_api, token, dirs, dest_dir, ext):
    """Compress each folder in `dirs` to <dest_dir>/<name>.<ext>, verify the archives are listed, ONLY THEN delete the folders.
    If dest_dir is inside a given folder, that folder's own sub-folders (minus dest_dir) are archived instead."""
    norm = lambda p: re.sub(r'^(~|/home/[^/]+)/', '', p.rstrip('/') + '/')
    dest_dir, out = dest_dir.rstrip('/'), []
    for d in dirs:
        inside = norm(dest_dir).startswith(norm(d))
        out += [x for x in list_paths(apis, app_name, list_api, token, d, 'directories') if not norm(dest_dir).startswith(norm(x))] if inside else [d]
    dirs = [d.rstrip('/') for d in out]
    ensure_nonempty('folders to archive', dirs)
    print('archiving:', dirs)
    made = []
    for d in dirs:
        target = join_path(dest_dir, d.rpartition('/')[2] + '.' + ext.lstrip('.'))
        res = _api(apis, app_name, compress_api)(access_token=token, directory_path=d, compressed_file_path=target,
                                                 delete_directory=False, overwrite=False)
        print('archived', d, '->', get_field(res, 'compressed_file_path'))
        made.append(target)
    listed = _api(apis, app_name, list_api)(access_token=token, directory_path=dest_dir, entry_type='files', recursive=False)
    gone = [t for t in made if not any(p.endswith('/' + t.rpartition('/')[2]) for p in listed)]
    if gone:
        raise RuntimeError('archives not found, sources kept: ' + str(gone))
    for d in dirs:
        _api(apis, app_name, delete_api)(access_token=token, directory_path=d)
    return made

def txns_involving(apis, app_name, list_api, token, emails, direction='both', **kwargs):
    """Transaction rows whose other party's email is in `emails`; direction 'sent'/'received'/'both' (de-duplicated;
    rows get _dir, _other). kwargs go to the API."""
    emails = {e.lower() for e in emails}
    rows, seen = [], set()
    for dr in (['sent', 'received'] if direction == 'both' else [direction]):
        for r in fetch_all_pages(apis, app_name, list_api, access_token=token, direction=dr, **kwargs):
            other = r['receiver' if dr == 'sent' else 'sender']['email'].lower()
            if other in emails and r['transaction_id'] not in seen:
                seen.add(r['transaction_id'])
                rows.append(dict(r, _dir=dr, _other=other))
    print('matching transactions:', len(rows))
    return rows

def has_account(apis, app_name, search_api, email, token=None):
    """True only if the search finds a user whose email EQUALS `email` (case-insensitive); fuzzy hits do not count."""
    kw = {'access_token': token} if token else {}
    return any(str(r.get('email', '')).lower() == email.lower() for r in fetch_all_pages(apis, app_name, search_api, query=email, **kw))

def play_song_in_collection(apis, app_name, play_api, queue_api, current_api, token, song_id, album_id=None, playlist_id=None):
    """Play ONE song of an album/playlist: play the collection, find the song in the NEW queue, play its queue_position,
    check the current song (raises if wrong). Pass the REAL ids (ints) and string API names."""
    if album_id is None and playlist_id is None:
        raise ValueError('pass album_id=... or playlist_id=... (the collection the song must be played from)')
    play = _api(apis, app_name, play_api)
    play(access_token=token, **({'album_id': album_id} if album_id is not None else {'playlist_id': playlist_id}))
    hits = [q for q in fetch_all_pages(apis, app_name, queue_api, access_token=token) if q['song_id'] == song_id]
    ensure_nonempty('song ' + str(song_id) + ' in that collection queue', hits)
    play(access_token=token, queue_position=hits[0]['position'])
    now = _api(apis, app_name, current_api)(access_token=token)
    print('now playing:', now)
    if isinstance(now, dict) and 'song_id' in now and now['song_id'] != song_id:
        raise RuntimeError('wrong song is playing: ' + str(now))
    return now

def library_song_ids(apis, app_name, token, song_api, album_api, playlist_api):
    """ONE flat set (union) of the song ids in my song, album and playlist libraries (a set subclass: len(), `in`, loops
    work; ids['songs'|'albums'|'playlists'] = one library's ids). Album/playlist rows carry song_ids."""
    parts = {}
    for key, api in (('songs', song_api), ('albums', album_api), ('playlists', playlist_api)):
        rows = fetch_all_pages(apis, app_name, api, access_token=token)
        parts[key] = {r['song_id'] for r in rows} if key == 'songs' else {i for r in rows for i in r['song_ids']}
    class _Ids(set):
        def __getitem__(self, key):
            return parts[key]

    out = _Ids(set().union(*parts.values()))
    print({k: len(v) for k, v in parts.items()}, 'union:', len(out))
    return out

def row_id(row):
    """The id of a list row whatever its key: id / song_id / album_id / playlist_id / artist_id (raises with real keys)."""
    for k in ('id', 'song_id', 'album_id', 'playlist_id', 'artist_id'):
        if k in row:
            return row[k]
    return get_field(row, 'id')

def song_details(apis, app_name, song_api, ids):
    """{id: show_song(song_id=id)} (play_count, rating, genre, release_date, duration...): library/album rows lack these."""
    return {i: _api(apis, app_name, song_api)(song_id=i) for i in sorted(ids)}

def queue_played(apis, app_name, queue_api, token, include_current=True):
    """Queue rows up to the current item by position (include_current=False: strictly before it)."""
    q = sorted(fetch_all_pages(apis, app_name, queue_api, access_token=token), key=lambda r: r['position'])
    cur = ensure_nonempty('is_current queue row', [r['position'] for r in q if r['is_current']])[0]
    return [r for r in q if r['position'] < cur or (include_current and r['position'] == cur)]

def update_my_review(apis, app_name, list_api, update_api, token, song_id, email, **fields):
    """Update MY one existing review of a song (rating/title/text); its id comes from the list filtered by email."""
    mine = [r for r in fetch_all_pages(apis, app_name, list_api, song_id=song_id, user_email=email)
            if r['user']['email'].lower() == email.lower()]
    ensure_nonempty('my review of the song', mine)
    print('updating review', mine[0])
    return _api(apis, app_name, update_api)(review_id=mine[0]['song_review_id'], access_token=token, **fields)

def prefix_plan(rows, fmt, year=None, other_dir=None):
    """(src, dst) pairs that put a date prefix on each file_dates row; fmt like 'YYYY-MM-DD_' or 'YYYY_MM_DD-'. With
    year+other_dir, files NOT created in `year` go to other_dir under their NEW name. Prints the plan; run move_checked once."""
    pairs = []
    for r in rows:
        pre = fmt.replace('YYYY', '%04d' % r['year']).replace('MM', '%02d' % r['month']).replace('DD', '%02d' % r['day'])
        pairs.append((r['path'], join_path(other_dir if year is not None and r['year'] != year else r['dir'], pre + r['name'])))
    print(*pairs[:60], sep='\n')
    return ensure_nonempty('prefix plan', pairs)

def month_plan(rows, root, by_month, default, year):
    """(src, dst) pairs sorting file_dates rows into root/<folder>/<name>: by_month = {2: 'A', 3: 'B'} applies ONLY to files
    created in `year` (the sandbox year); every other file (other month OR other year) goes to `default`. Prints the plan."""
    pairs = [(r['path'], join_path(root, by_month.get(r['month'], default) if r['year'] == year else default, r['name']))
             for r in rows]
    print(*pairs[:60], sep='\n')
    return ensure_nonempty('month plan', pairs)

def unpaid_shares(apis, app_name, list_api, token, shares, **kwargs):
    """shares = {email: amount owed}. Prints a table and returns [(email, amount)] of people with NO received payment from
    them; kwargs = date window for the API (min_created_at=, max_created_at=). Rows are matched by sender email."""
    got = {r['_other'] for r in txns_involving(apis, app_name, list_api, token, shares, direction='received', **kwargs)}
    print(*[(e, a, 'PAID' if e.lower() in got else 'unpaid') for e, a in shares.items()], sep='\n')
    return [(e, a) for e, a in shares.items() if e.lower() not in got]
