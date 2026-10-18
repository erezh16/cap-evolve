## Skill: appworld_data_extraction_and_answer_hygiene

---
name: appworld_data_extraction_and_answer_hygiene
description: Rules for reading values out of files/records (bill totals, sums), login and parameter gotchas, date handling, and complete_task answer format in AppWorld.
---

## When to Apply
- Any task that computes an answer (sum, total, count, max) from file contents, notes, emails, or API records.
- Any task using file_system, phone, or venmo APIs (login and parameter gotchas).
- Any task that depends on "today", "yesterday", "this year/month".
- Every task, when calling `apis.supervisor.complete_task`.

## When NOT to Apply
- Spotify read-only max/min queries that already work with the normal recipe (but still follow the answer-format rules in section 5).

## Instructions

### 1. Never parse a file you have not looked at
- Before writing a regex, `print(repr(content))` for 1-2 files (one of each extension, e.g. .txt and .pdf). Find which line holds the wanted value (e.g. a line with "Total"/"Amount due"/"Amount").
- DO NOT run a generic number regex over the whole text and take the first match: it grabs a year, date or account number. A past run returned a sum equal to 4 files x 2023 (the year). Anchor on the label or the `$` sign, e.g. `re.findall(r'\$\s*([\d,]+\.\d{2})', line)` on the line containing the label; strip commas.
- Print the per-file (filename, parsed amount) list and sanity check: amounts must look like plausible currency values and differ between files.

### 2. Scope files precisely
- Bill folders can contain both `YYYY-MM.txt` and `YYYY-MM.pdf` for the same month. Inspect a .pdf's `content` to see whether it duplicates the .txt; if so count each month once (prefer .txt). Print the number of distinct months counted.
- "This year" = the year of the simulated current date, NOT the machine clock (`datetime.now()` is wrong). Use `apis.phone.get_current_date_and_time()`, which returns `{'date': 'Thursday, May 18, 2023', 'time': '10:10 PM'}`; year = `int(d['date'].split(', ')[-1])`. Print the raw output first. Filter filenames by the `YYYY-` prefix of that year; ignore other years and other categories (cable/internet/phone/electricity: use only the category asked).
- For "today"/"yesterday": `datetime.strptime(d['date'].split(', ',1)[1], '%B %d, %Y')`, then compare dates only.

### 3. file_system API facts
- Login first: `apis.supervisor.show_account_passwords()` -> entry with `account_name == 'file_system'`; `apis.file_system.login(username=<email from apis.supervisor.show_account()>, password=...)`; pass `access_token=` to every call.
- `show_directory(access_token, directory_path, substring, entry_type, recursive)`; `entry_type` must be 'all', 'files' or 'directories' (not 'file'). There is NO `path` param. `~` works in directory_path; results are absolute paths (`/home/<user>/...`). Use `recursive=True, entry_type='files'` on the exact sub-folder.
- `show_file(access_token, file_path)` returns a dict; text is in `['content']`.
- Never pass `access_token=None`. When an error says unexpected parameter, call `apis.api_docs.show_api_doc(app_name=..., api_name=...)` rather than guessing.

### 4. Login gotchas
- Phone login username = phone NUMBER (from `supervisor.show_account()`); venmo/spotify/gmail/file_system etc. use email. Re-fetch passwords inside the same code cell where you use them (variables from failed cells may not exist).

### 5. complete_task answer
- Answer must be a plain str/int/float (a list gives a 422). For questions answer with just the value (number without currency symbol/units, title/name only, as requested). Round money to 2 decimals.
- For action tasks (like, send, update, delete, create, move...) call `apis.supervisor.complete_task()` with NO answer. Never invent a count or list as the answer after a validation error.
- Do state-changing calls only after printing the computed target set; never swallow exceptions around writes.

### 6. Spotify: "play the most/least listened song of <album|playlist>" and "recommended" songs
- Public catalog calls take NO access_token: `search_albums`, `search_songs`, `search_artists`, `show_album`, `show_song`. Library, playlist-write, queue and player calls need it. Pick the album by EXACT title match in `search_albums` results (an album title is not an artist name; results have an `artists` list, no `artist` key). For "my" playlist use `show_playlist_library(access_token, query=..., page_limit=20)` and match the title exactly.
- Songs: `show_album(album_id)['songs']` / `show_playlist(playlist_id, access_token)['songs']` (key `id`). Do NOT rebuild an album's songs from `search_songs`. Counts: public `show_song(song_id)['play_count']` (`show_song_privates` has none). Print (title, play_count) for every song, then take min/max.
- Past runs picked the right song, called only `play_music(song_id=best)` and then complete_task, yet the grader failed all of them (it checks that the current player song is the target AND belongs to the album/playlist collection). Do this instead: (1) `play_music(access_token, album_id=...)` or `playlist_id=...` so the whole collection is queued; (2) `q = show_song_queue(access_token)`, find the entry whose song id == target and read its `position`; (3) `play_music(access_token, queue_position=pos)`; (4) verify with the player-state / current-song API (look up its name via `show_api_descriptions('spotify')`) that the current song id == target id; print it. Only then call `complete_task()` with no answer.
- "Spotify-recommended songs" means the `show_recommendations(access_token, page_index, page_limit=20)` API (paginate until empty), NOT `search_songs`. Its items lack genre/release date: call `show_song(song_id)` for each and filter on `genre` (case-insensitive) and the `release_date` year (year from `apis.phone.get_current_date_and_time()`). Create the playlist, add exactly the filtered set, and print the set first.

### 7. "Reply to <person> with items from my notes AS PER THEIR REQUEST" (text-message reply tasks)
Past runs (3 of 3) sent the WHOLE note list and failed the check that titles not matching the person's criterion must be absent from the sent message. The request is inside the person's incoming text message, which the runs never read.
1. Phone login username = phone number (`apis.supervisor.show_profile()['phone_number']`); pass `access_token=` to every phone call. Find the contact with `search_contacts(access_token, query=<first name>, page_limit=20)`; pick the entry whose first_name matches exactly and take its `phone_number`.
2. READ THEIR MESSAGE FIRST: `apis.phone.search_text_messages(access_token=..., phone_number=<contact number>, page_limit=20)` (check `show_api_doc` for exact params). Print the messages and identify the latest one received from them. Extract the exact criterion (e.g. movies by a given director, a genre, a count). Do not guess the criterion from the contact's first name or from similarly named people/directors.
3. Find the note via `search_notes` (paginate, page_limit=20); use a `note_id` that appeared in the printed results (never invent one), then `show_note` and `print(note['content'])`. Notes of this kind are blocks like `Title\n - director: X\n - genre: A, B`. Parse each block into (title, attributes), keep only blocks whose attribute matches the criterion (exact, case-insensitive; for 'director' compare the `director:` line only; 'Joel and Ethan Coen' style values may list several names, so use substring match on the name), de-duplicate titles keeping order.
4. Print the filtered titles and the count BEFORE sending. The message should be just the comma-separated titles (`', '.join(titles)`), no extra sentence, so no excluded title can appear inside it.
5. `send_text_message(access_token, phone_number=..., message=...)` once, then `complete_task()` with no answer.
