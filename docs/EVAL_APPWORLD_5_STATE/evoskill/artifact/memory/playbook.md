## appworld-api-playbook: Workflow checklist for AppWorld tasks where Python is written against apis.<app>.<api> and finished with apis.supervisor.complete_task. Covers API specs, per-app login, sandbox limits, pagination, CSV output, verifying intermediate data, answer semantics and destructive-action ordering.

# AppWorld API Playbook

Follow these steps in order.

1. **Read each spec before calling an API.**
   Run `apis.api_docs.show_api_doc(app_name=..., api_name=...)` for every API you will use. Copy parameter names exactly; never guess.
   - Common mistakes: `path` vs `file_path`/`directory_path`; passing `access_token` to `show_song`, `show_album`, `show_song_reviews` (they take none); invented APIs like `create_folder`/`write_file`.
   - Pass `access_token` only where the spec lists it.

2. **Handle auth per app.**
   - Credentials: `apis.supervisor.show_account_passwords()`.
   - Log in to each app separately (e.g. spotify, file_system); tokens differ.
   - Username per app:

     | App | username |
     |---|---|
     | phone | the PHONE NUMBER from `apis.supervisor.show_profile()['phone_number']` (the email gives 401 "Invalid credentials"; two traces lost 2-4 steps to this) |
     | spotify, venmo, file_system, gmail, other apps | the email from `apis.supervisor.show_profile()` (or the email in the task) |

   - If a login returns 401, run `show_api_doc` for that app's `login` and read the `username` description.
   - Phone-app calls (e.g. contact lookup) need a phone token, so log in to phone first.
   - `apis.phone.get_current_date_and_time()` takes NO args; passing `access_token` raises an error.
   - Store tokens in variables (`spotify_token`, `fs_token`); never retype them.

3. **Respect sandbox limits.**
   - `os`, `io`, and `open` are blocked. Write files only via `apis.file_system.create_file(file_path=, content=, overwrite=True, access_token=)`.
   - Do not import `io`/`os`, and do not use `csv.writer` (it fails even on a custom list-backed writer). Build rows with a manual `quote(field)` helper (wrap in double quotes if the field has `,`, `"` or a newline, and double any inner quotes) and join with `'\n'`. Never write to disk directly.

4. **Paginate correctly.**
   - Loop `page_index` (from 0) with `page_limit=20` (or the spec's max) until an empty page is returned.
   - Don't stop on `len < limit` unless the page size is confirmed.
   - Check each endpoint's pagination params in its spec.

5. **Gather data completely.**
   - Songs in "library, album library, and playlists": `show_song_library`; `show_album_library` then `show_album` per album (use `songs`); `show_playlist_library` then `show_playlist` per playlist (use `songs`).
   - Consider whether liked/downloaded collections are implied.
   - Dedupe on exact (title, artists) as given. Don't lowercase, re-sort, or reorder artists.
   - **Spotify "newest/oldest/most/least across song, album and playlist libraries" recipe:**
     - Library entries use their own id key; print `song_lib[0]`, `album_lib[0]`, `playlist_lib[0]` first.
     - `show_album` and `show_playlist` return `songs` (list of dicts with `id`), NOT `song_ids`. (A failed run used `.get("song_ids", [])` again, got nothing, and still answered.)
     - `show_playlist` needs `access_token` for private playlists (422 otherwise).
     - Song release dates come from `show_song(song_id)`; album songs lack `release_date`. Call `show_song` per id, or use the album's `release_date`.
     - Before `complete_task(answer=...)`, print the distinct-song count from each of the three sources and the top 3 candidates with dates. If the album or playlist count is 0, stop and debug.
   - **Library listings are summaries, not details.** `show_playlist_library`, `show_album_library` and `show_song_library` rows do NOT contain `songs`. Print `playlist_lib[0]` to find the id key (index with `[key]`, not `.get`), then call `show_playlist` (or `show_album`) per id and iterate `detail['songs']`.
     ```python
     song_ids = set()
     for pl in fetch_all(apis.spotify.show_playlist_library, access_token=tok):
         detail = apis.spotify.show_playlist(playlist_id=pl['playlist_id'], access_token=tok)
         song_ids |= {s['id'] for s in detail['songs']}
     songs = [apis.spotify.show_song(song_id=i) for i in song_ids]  # no token; genre is top-level `genre`
     artist_ids = {a['id'] for s in songs if s['genre'] == genre for a in s['artists']}  # artists: list of dicts
     ```
     Then assert non-empty and act (e.g. `follow_artist`). `show_following_artists` rows use `artist_id`, not `id`; print `rows[0]` before building a set from it.
   - **Per-entity predicates: liked / downloaded / library cleanup.**
     - Apply each qualifier to its own entity type. Check `show_api_descriptions('spotify')` BEFORE coding for per-entity lists (`show_liked_songs`, `show_liked_albums`, `show_liked_playlists`, `show_downloaded_songs`); map each noun ("liked", "downloaded") to its own list per entity.
     - "Keep songs and albums I liked/downloaded": copy the connective (AND/OR) from the task wording. Song: "liked or downloaded" = `liked_ids | downloaded_ids`; "liked and downloaded" = `liked_ids & downloaded_ids`. Album, same connective: `album_liked` = album_id in `show_liked_albums`; `album_downloaded` = ALL its songs are in the DOWNLOADED song ids (not liked ids, not the song keep-set). "or" = album_liked OR album_downloaded; "and" = album_liked AND album_downloaded.
     - Before coding, write the task's connective (AND/OR) in a comment for songs and for albums, e.g. `# album keep = album_liked <AND|OR> album_downloaded`. Do not copy a keep-rule from an example whose wording differs. Print the per-album table (album_id, in_liked_albums, n_songs, n_downloaded) so each decision is visible.
     - Id keys: library/liked/downloaded song rows `song_id`; nested `songs` in `show_album`/`show_playlist` use `id`; library album rows `album_id`. Print `rows[0]` of each, index with `[key]`. `show_album` takes only `album_id`, no access_token.
     - Removal: `remove_song_from_library` / `remove_album_from_library` (no `delete_song`/`delete_album`). Confirm names in the descriptions once.
     - Cleanup phase split: cell 1 is read-only; print `(kept songs, removed songs, kept albums, removed albums)` counts and the per-album table, and check each rule against the task wording. Remove in a later cell, then `complete_task()` with no answer.

6. **Format outputs exactly as the task says.**
   - CSV: proper quoting (titles with commas break `f"{title},{artists}"`), exact header, artists joined by `|`. Row order is not required.

6b. **Resolve the real requirement from the data, not from the task sentence alone.**

   A. **"X asked me for ... via text/email/note"** means the criteria are INSIDE X's message. Before acting:
   - Log in to phone, find the message with `phone.search_text_messages` or `show_text_message_window` (or the gmail equivalent), page through results and print the message text.
   - Pull the filter out of it ("movies directed by Christopher Nolan", "only the sci-fi ones", "top 3").
   - Apply that filter to the source data. If the source note has per-item attributes (`- director:`, `- genre:`), filter on them. Never dump the whole list.
   - Print the filtered list and its count BEFORE sending the reply.
   - Reply in the format asked. For "comma-separated titles": titles only, no metadata lines, deduped.

   B. **Several candidate notes/files/emails** (e.g. two "Work Dinner" notes):
   - Print title, `created_at` and the first lines of EACH candidate.
   - Pick the one matching the task's time or entity ("yesterday" = created/dated yesterday; or the venue the task names).
   - Do NOT merge or sum candidates unless the task says so. (A run summed two dinners' shares, Sabrina 39+21=60, and requested wrong amounts.)
   - If ambiguous, compare dates against `get_current_date_and_time()`.

   C. **Splitting a bill / collecting money (Venmo requests):**
   - Match each person in the note to a contact by full name or relationship group (`search_contacts`), not first name only. Print the name-to-email map.
   - Compare against payments already received IN THE RIGHT WINDOW (use the `show_transactions` spec; don't invent `direction=`). Request only from people who have not paid their share.
   - Print `(name, owed, paid, request)` for every person before sending any request.
   - Use the exact description the task gives.

7. **Verify intermediate data before acting.**
   Wrong or incomplete intermediate data is the main cause of failures; check it before any side effect.

   A. **Print one sample record before parsing.** For each new endpoint run `print(response[0])` or `print(list(resp.keys()))` and match field access to the spec's response_schemas.
   - **Hard rule:** for API response dicts always index with `[key]`. Never `.get(key, [])` or `.get(key)` in a loop that feeds an answer or a write, so a wrong key raises. (`album.get('song_ids', [])` hid that the field is `songs`, silently dropping songs.)
   - Guard before the `complete_task` or write cell: `assert len(items) > 0, "empty - wrong key or source?"`.
   - Know the shape: `phone.get_current_date_and_time()` returns `{'date': 'Thursday, May 18, 2023', 'time': ...}`, NOT ISO. Comparing `created_at.split('T')[0]` to it matched nothing.
   - Parse dates deliberately, e.g. `datetime.strptime(s, '%A, %B %d, %Y').date()`, compare date objects, and print both sides of the first comparison.

   B. **Paginate EVERY list endpoint**, including `phone.search_contacts`, `show_transactions`, `show_social_feed`, library/playlist lists. Loop `page_index` until a page is empty, `page_limit=20`. The default page_limit is 5: an unlooped `search_contacts(relationship='coworker')` returned only 5 contacts and coworker payments were missed. Write `fetch_all(fn, **kw)` once and use it for every list call.

   C. **Sanity-check counts before side effects.**
   - Print sizes of intermediate sets (contacts found, candidate transactions, song ids) and the coworker/roommate emails.
   - If a set the task implies is non-empty ("all transactions from today with roommates", "payments from coworkers in the last 5 days") is EMPTY or suspiciously small, STOP. Debug date parsing, filters and pagination. Do NOT call `complete_task`. (One run printed "Transactions to like: []" then called `complete_task()` anyway and scored 0.)
   - **Zero-count tripwire:** if ANY intermediate set the task implies is non-empty (songs in 8 playlists, contacts, transactions) has len 0, do NOT run the write loop or `complete_task`. Add `assert len(song_ids) > 0, "empty - library rows lack 'songs'? use show_playlist"` before the write cell. Two runs printed "8 playlists / 0 song IDs / 0 artists", followed nobody, and still completed; one "fixed" an unrelated error and ignored the 0.
   - Do identification and printing in one cell; do like/comment/delete/`complete_task` in a later cell after checking the output.
   - Don't wrap writes in `try/except: pass`; it hides failures.
   - Before `complete_task`, ask: did I apply EVERY condition in the task sentence (who, when, which subset, format)? List each condition and the line of code that enforces it.

   D. **Date/time windows.**
   - Get "today" from `apis.phone.get_current_date_and_time()` (no access_token), NOT `datetime.utcnow()`; the sandbox clock differs from the simulated date.
   - "Last N days including today": start = today - (N-1) days, inclusive on both ends.
   - Prefer the API's `min_created_at`/`max_created_at` filters (YYYY-MM-DD) and also print the `created_at` of matched rows.
   - Check the spec for `show_transactions` params; don't guess names like `direction`. For "received from X", also check `receiver.email` == me and `sender.email` in the target set.
   - `# show_transactions has NO direction param: unknown kwargs are silently ignored. Filter client-side: txn['receiver']['email']==my_email and txn['sender']['email'] in contact_emails`. Several runs repeated this error: they passed `direction='received'` and got both sent and received transactions. The "received" check must be explicit in the filter, and a `print` of 3 sample rows (sender, receiver, created_at) must precede the like/comment loop. Identification and writes go in separate cells; the failed run combined them.

   E. **Relationship groups.**
   - Roommates, coworkers etc. come from `phone.search_contacts(relationship=...)`; valid values come from `show_contact_relationships`. Collect `email` and keep `phone_number`.
   - "My friends", "siblings", "roommates", "coworkers" means phone contacts: `phone.search_contacts(relationship='friend')` (paginated, check `show_contact_relationships`). Do NOT use `venmo.search_friends` unless the task says "Venmo friends". A run that used it for "payments from my friends" liked and commented on 25 transactions and failed the exact-set check. Log in to phone with the phone number, build the email set from contacts, and print the count and emails.
   - Venmo participants are identified by email. If a contact's email matches no transaction sender/receiver email, fall back to matching on name.

   F. **Likes and comments.** Skip transactions already liked by me (use the `liked` flag if the spec lists one). Don't comment twice. Apply both actions to exactly the same filtered set.

8. **Answer semantics.**
   - Action-only tasks (rate, delete, export, etc.): call `apis.supervisor.complete_task()` with no answer (or `answer=None`). Do not pass counts or file paths. "Follow all artists ..." is an action task: `complete_task()` with no answer (a run passed `answer=followed_now` and failed).
   - Question tasks: pass a minimal bare value (number or string), not a sentence.

9. **Destructive actions last, verified first.**
   - Before `delete_account` (e.g. "back up, then terminate"), read the file back with `show_file` and check the row count.
   - Build stages in small verified steps; combine into one script only afterwards. A failed run can leave partial state (e.g. account already deleted).
   - Make steps idempotent: `overwrite=True`, `allow_if_exists=True`.
   - **Account termination targets the app named in the task.** "Terminate/delete my account" after a backup or export means the account of the app the data came from (if no app is named, the app whose data was exported). E.g. after "export my Spotify songs ... terminate my account": `apis.spotify.delete_account(access_token=spotify_token)`. NEVER call `file_system.delete_account`: the file system only holds the backup, and deleting its account destroys the file.
     - Before the delete cell: `show_file` the CSV, print the row count and first 3 lines, and check the row count equals the number of unique (title, artists) pairs. Write the header exactly as given (e.g. `Title,Artists`).
     - Call `delete_account` only in a later cell, then `complete_task()` with no answer.

10. **Spotify ratings/reviews.**
    - Before `review_song`, check for an existing review by the user. `show_song_reviews(song_id, user_email=...)` may miss it; fall back to `show_song_review` or the user's reviews list.
    - Exists → `update_song_review`; otherwise `review_song`.
    - "Songs I liked" = `show_liked_songs`. "In my playlists" = every playlist in the library.
    - `rating=5` as an integer.
    - **Review lookup must be exhaustive and visible** ("rate all songs X, raise it if already rated lower"):
      - Never trust one `show_song_reviews(song_id, user_email=...)` call with an empty result as "no review". Page through `show_song_reviews(song_id=..., page_limit=20)` until a page is empty and keep rows where `row['user']['email'] == my_email`.
      - Build the target set with the task's exact qualifiers. E.g. "songs in my album library which I liked" = song ids from `show_album` per album (`songs[*]['id']`) intersected with liked ids (`song_id`); print both set sizes and the intersection. If it could mean liked albums, check `show_liked_albums` and note in a comment which reading applies.
      - Per song: rating < target → update; already >= target → skip; no review → add. Print a plan table `(song_id, existing_review_id, existing_rating, action)` plus counts of each in a read-only cell before any `review_song`/`update_song_review`. Then `complete_task()` with no answer.

11. **Debug economically.** On an exception, print the spec for exactly that API, fix parameter names, and re-run only the failing stage. Don't rewrite the whole pipeline.

## Examples

Manual CSV builder (no `io`, no `csv.writer`):
```python
def quote(field):
    s = str(field)
    if any(c in s for c in ',"\n'):
        s = '"' + s.replace('"', '""') + '"'
    return s

rows = ["title,artists"] + [f"{quote(t)},{quote('|'.join(a))}" for t, a in songs]
csv_text = "\n".join(rows)
```

Reusable pagination helper:
```python
def fetch_all(fn, **kw):
    out, page = [], 0
    while True:
        batch = fn(page_index=page, page_limit=20, **kw)
        if not batch:
            return out
        out += batch
        page += 1

coworkers = fetch_all(apis.phone.search_contacts, relationship='coworker', access_token=phone_token)
```

Print the set, then act (two cells):
```python
# Cell 1: identify and print only
today = datetime.strptime(apis.phone.get_current_date_and_time()['date'], '%A, %B %d, %Y').date()
# show_transactions has NO direction param: unknown kwargs are silently ignored. Filter client-side: txn['receiver']['email']==my_email and txn['sender']['email'] in contact_emails
txns = [t for t in fetch_all(apis.venmo.show_transactions, access_token=venmo_token) if ...]
print([(t['sender']['email'], t['receiver']['email'], t['created_at']) for t in txns[:3]])
print(len(coworkers), [c['email'] for c in coworkers])
print(len(txns), [t['created_at'] for t in txns])
# If empty or suspiciously small: STOP and debug.

assert len(txns) > 0, "empty - wrong key or source?"

# Cell 2 (only after checking output): act on exactly `txns`
for t in txns:
    apis.venmo.like_transaction(transaction_id=t['id'], access_token=venmo_token)
apis.supervisor.complete_task()
```

Finish:
```python
apis.supervisor.complete_task()          # action-only task
apis.supervisor.complete_task(answer=42) # question task
```