## Workflow

## Workflow

1. Read the task literally and list every requirement: apps, entities, filters and thresholds, scope qualifiers ("all", "any", "only", "so far", "and" vs "or", sent vs received), date window (month AND year), counts, ordering, fallbacks ("the others"), containers named (library, playlists, etc.), the exact metric wanted, and the output format. Decide whether it is a question (needs an answer value), an action-only task, or both, and which irreversible step must come last.
2. Discover APIs before using them: `apis.api_docs.show_app_descriptions()`, `apis.api_docs.show_api_descriptions(app_name=...)`, then `apis.api_docs.show_api_doc(app_name=..., api_name=...)` before the first call of EVERY API. Note exact parameter names, required parameters, whether `access_token` is needed, enum values, pagination limits and the response schema. If doc output is truncated, print it in slices. Never guess API names, parameters or response fields.
3. Authenticate where needed (see Authentication).
4. Work in small, syntactically complete REPL steps, one phase per cell (login, fetch, inspect, select, act). The REPL does not echo bare expressions, so `print(...)` what you rely on (keys, counts, ids, dates, one sample record, write responses). A cell showing only "Execution successful." means nothing was verified. Avoid one long multi-phase script; a half-written script can finish "successfully" and skip a phase.
5. Inspect real state before acting. List or fetch actual contents first; the task's description may not match reality.
6. Turn vague requirements into measurable ones (e.g. "long enough for an activity" means compare total duration in minutes with the activity's duration).
7. Prefer built-in options that fold steps into one call (e.g. a delete-source flag on a compress API) over manual chains, but verify the result.
8. Select, then act, then verify, then call `apis.supervisor.complete_task(...)` once, in its own final step.

## Authentication

## Authentication

- Get credentials from `apis.supervisor.show_account_passwords()` (select by `account_name`) and the user's email/phone from `apis.supervisor.show_profile()`. Never invent credentials or ask the user for them.
- Log in to each app separately with its `login` API. Check the doc for the username field (email vs phone number). If login fails with 401 invalid credentials, retry with the other identifier and the same password.
- Keep tokens in named variables. Pass `access_token` only to APIs whose doc lists it; some public endpoints reject it with "Unexpected parameter". A later 401 usually means a missing or stale token.
- If variables are lost (NameError), re-fetch credentials and log in again in one self-contained snippet:
```python
passwords = {p['account_name']: p['password'] for p in apis.supervisor.show_account_passwords()}
tok = apis.<app>.login(username=<email>, password=passwords['<app>'])['access_token']
```
- Do not spend steps on unrelated apps.

## API Usage and Data Discipline

## API Usage and Data Discipline

- Pass only documented parameters. Omit optional parameters rather than passing `None`, and do not set optional ones the task did not mention.
- Never guess field names. Read the response schema or print one real record (`print(obj)`, `obj.keys()`) before writing logic on it. Check types (list vs dict, ids vs nested objects) before indexing. Index keys directly; avoid `.get(k, default)`, `continue`, or broad try/except that hide mismatches. If a lookup is None/empty or raises KeyError, stop, print the raw record and re-read the doc.
- Before filtering by an attribute (genre, category, label, status), print the real distinct values and match against them; check casing and units (seconds vs minutes). Aggregate in the raw unit and convert/round once at the end. Compare lowercased strings or use substring checks to tolerate formatting.
- Map each task criterion to a dedicated API parameter when one exists (genre, min/max, date range, sender/recipient, direction, user, sort) instead of free-text `query`. If no filter exists, fetch all candidates and filter in Python on printed fields; check whether bounds are inclusive. Try a filter before assuming data is missing.
- For latest/first/most/top questions, prefer server-side `sort_by` (e.g. `-field` for descending) with `page_limit=1`, or sort by an explicit timestamp field in code. Do not rely on default order.
- Chain lookups through IDs: resolve a name to an ID with a search API, then use the ID in the next call. If a KeyError occurs, check which identifier links the lookup API to the action API.
- List endpoints often return only ids, paths or summaries. Reuse nested data already present; call the item's detail endpoint (`show_*`) for missing authoritative attributes (dates, genre, duration, full text, contents) and cache by id. An attribute may live on a parent object; do not substitute it unless the docs say they are equivalent.
- List endpoints may return records of all users. Filter by the current user's id/email (documented parameter, else in code); a 422 "does not belong to you" means you chose another user's record. For own reviews/comments select by an ownership field, not by index.
- Parse source data (notes, files, messages) into structured records and keep attributes until all criteria are applied. Print the full content in its own step before writing a parser. Locate the labeled field ("Total", "Amount due"); never regex the first number. List all files including duplicates in other formats and use one readable copy per record; print per-file extracted values and the running total.
- Output may be truncated: print compact summaries (counts, `Counter`, slices) and never assume the hidden part matches the visible part.
- On an error, read the message (it often lists allowed parameters), re-read that API's doc and fix the actual cause. Do not retry the same call or random variants. After a mid-script failure, do not trust variables from the partial run; rebuild or print counts first.
- Use only the provided `apis.*` interface and plain Python. Modules like `os`/`io` may be blocked; use the file_system app and check its doc for parameter names.

## Pagination and Aggregation

## Pagination and Aggregation

- Every list/search API is paged with small defaults. Pass the largest allowed `page_limit` and loop `page_index` from 0 until a page is empty (or shorter than the limit). Never rank, filter, count or conclude "does not exist" from the first page. Print the total count.
```python
def fetch_all(fn, page_limit=20, **kw):
    out, i = [], 0
    while True:
        r = fn(page_index=i, page_limit=page_limit, **kw)
        if not r: break
        out.extend(r)
        if len(r) < page_limit: break
        i += 1
    return out
```
- For most/least/top/count/sum questions, compute in code (`Counter`, `sum`, `max`, `min`, `sorted`) over the full dataset. Count every entity on each item (e.g. every artist on a song). Check ties and exact wording (most vs least, own library vs global).
- When a question spans several sources (library, playlists, albums, liked, text and voice messages, multiple accounts), enumerate each, merge ids into a set to dedupe, then fetch details once per id. Evaluate each container independently from its own items. Print per-source counts and the total; investigate any unexpected zero. Inspect near-duplicates before deduping.
- Set logic: for "keep only items satisfying A and B", build id sets from fully paginated lists and act on `library - (A & B)`. For composite properties (e.g. "album is downloaded"), fetch children and test `set(child_ids).issubset(flagged_ids)`; treat empty containers as not satisfying it.
- A suspiciously small or empty result for a plural noun usually means missed pages, a wrong field, wrong auth or wrong direction. Investigate before accepting it.

## Requests, Scope and Entity Resolution

## Requests, Scope and Entity Resolution

- If the task refers to what someone "asked", "requested" or "wants", first find and read that original message (texts, email, chat, notes; search then a detail call for the full text). Extract every constraint and filter by it. Never assume it means "everything". Reply on the same channel unless told otherwise.
- Turn each scope qualifier into an explicit filter. When the task names two collections, fetch both and compute the intersection/union by id as worded. For "so far", "before", "up to and including the current one", filter on an explicit boundary field (current index, played flag, date) and include the boundary item only if the task says so.
- Words like "move", "update", "change", "delete", "my X" imply the item exists. If a literal search finds nothing, list all candidates and match by meaning (time, label, repeat pattern, recipient); the task may paraphrase the stored label. Create new records only when asked to add something.
- Match the API to the task verb (e.g. "request money" is a payment-request API, not send-money). Read the spec of any better-fitting API first.
- "My" or user-specific wording (most listened, favorites, history, library) means user-scoped APIs (`*_library`, `*_history`, docs saying "private to the user"), not public aggregates like global play_count.
- Never take `results[0]` unexamined. Print names and key fields of all candidates, pick the exact match, and confirm its content fits the task. If follow-up calls return empty or odd data, suspect the wrong entity. If search returns nothing, change strategy (another endpoint, spelling, filters, pagination) before concluding it is missing. Never invent a missing value.
- Decide what kind of entity a name is from context (in music tasks a person name is usually an artist: use artist/song search first).
- When several records plausibly match (multiple notes/files on a topic), pick the one fitting the task's time and context by comparing dates and details; do not merge or sum across them.
- Names to identifiers: print the full mapping for every name from a note or list, including multiple matches and misses; never silently drop items. Try full name, other fields, other apps, and relationship cues; do not take the first match for a bare first name.
- Relationship groups (roommates, family, friends, coworkers, manager) come from Phone contacts: `apis.phone.search_contacts(relationship=..., page_index=...)` with full pagination. List available relationship values and include every relevant variant (e.g. both sibling labels). Reconcile with app-specific lists (e.g. payment friends). Match people across apps by exact email or phone number, not name alone; print unmatched people and the resolved group and its size before using it.
- Do not infer a status (paid, done, sent, liked) from a person's mere presence in history. Match on counterparty AND amount AND date window AND description; treat mismatches or partial amounts as not settled. If one source lacks the record, fall back to a related source that records the outcome (e.g. transaction history).
- When splitting a cost, include the user (total / (others + 1)) unless told otherwise; round money to 2 decimals and keep numbers as numbers. Decide the metric (absolute, net, sent vs received) from the wording and check sign conventions in the data. Reuse values from earlier records (amount, description, recipient) from API responses, not memory.

## Dates and Time

## Dates and Time

- The simulated clock can differ from the system clock. Do not rely on `datetime.now()` for "today", "yesterday", "last week", "this month/year", and never hardcode years. Take the reference date from `apis.phone.get_current_date_and_time()` (print the raw result first for key names and format) or other time API, else from the latest app data. Cross-check against timestamps seen in outputs and print the date you use. If a computed date contradicts the data (e.g. different year), re-derive it.
- Parse with `datetime.fromisoformat`/`strptime` matching the documented format (e.g. zero-padded `HH:MM`, YYYY-MM-DD for filters). Compare year AND month, not just a month name. Print sample timestamps, min/max dates and boundaries; inspect items just inside and outside the window.
- "Last N days including today": min = today - (N-1) days, max = today. Handle wraparound with modulo (e.g. `(hour + 1) % 24`). Compute derived times ("+20 minutes") from the existing stored value.
- Fetch with a generous range and filter on printed dates rather than one exact day. If data does not fit the expected period, re-examine your interpretation instead of silently substituting another period.
- Make fallback categories ("the others") an `else` branch so nothing is dropped; if everything lands in one bucket, recheck the logic.

## Safe Writes and Bulk Operations

## Safe Writes and Bulk Operations

Applies to send, pay, request, delete, remove, unfollow, cancel, like, follow, add, create, update, post, approve.

- Separate select from act. Build the candidate set in its own step (all pages, all containers, ids in a `set` to dedupe) and print a table: item/person, expected amount or content, the deciding evidence fields, and act/skip with a reason; also print excluded near-misses. Act only in a later step. Never loop over unseen data or perform side effects inside a loop over partial data.
- For "all"/"any" conditions, check every element of the detail data, not summary fields. For "all except set Y", build the exclusion id set first.
- Sanity-check counts: an empty or all-inclusive set signals a schema or logic error; investigate before acting.
- Build outgoing content (messages, amounts) in a variable, print it, and pass the variable. Take recipients, amounts and targets from fetched data.
- Make writes idempotent: check existing state first (already followed/liked/added, existing record, sufficient balance), skip items already in the target state, and update an existing record instead of creating a duplicate (a 409 "already exists" on create means find and update it). Send each message or payment once. Pre-check endpoints can be unreliable, so also wrap each write and treat an "already done" error as success while re-raising others:
```python
for item_id in sorted(target_ids):
    try:
        apis.<app>.<write_api>(item_id=item_id, access_token=token)
    except Exception as e:
        if "already" not in str(e).lower():
            raise
```
- Collect all ids before mutating, since offsets shift while paging and deleting. Create destination containers (directories, playlists) before moving/adding. Keep original names unless told otherwise.
- Stage file work: create outputs first, verify each exists at the exact required path (full path vs name, trailing slash, exclude output folders), test on one entry, and only then delete/overwrite sources in a separate step. Avoid blanket flags like `delete_directory=True` or `overwrite=True` until outputs are verified.
- Never use bare `try/except: continue` or silent guards that skip work. Print every skipped item and failure. Print each write response or success/failure counts; a `message` key or truthy response is not proof of success.
- If a script with writes crashes, do not re-run it blindly; re-fetch current state to see which writes happened and continue only with the remainder.
- Keep irreversible steps (account deletion, bulk delete, sends, payments) last, only when the task asks and only after verification. Never combine the irreversible call and `complete_task` in one script.
- Do only what the task asks; no extra writes or side effects.

## Finding and Editing Existing Items

## Finding and Editing Existing Items

- Search/list APIs often return metadata only. Fetch the full item (e.g. `show_note`) to read the body before editing.
- If no exact title match exists, the item may be a line inside a container note or list (e.g. a checklist). Open candidates by title/tag fit and read full content. When the task refers to a note/file/playlist, choose the entry matching its context (weekday, date).
- Read the item's conventions first (legend, markers such as `[x]` done vs `[ ]` not done) and match the existing format.
- Update calls usually replace the whole content. Fetch current content, change only the target part (string replace with enough of the line to be unique), and write back everything else unchanged, passing existing title, tags and other fields so nothing is lost.
- Check the response, then re-fetch to confirm only the intended change landed.

## Verification

## Verification

- After any change, re-query state via read APIs covering all pages: confirm count, ids, recipients, amounts, descriptions and dates match the task, with nothing omitted, duplicated, extra or unintentionally changed. A "0 remaining" check is valid only if it covered all items and pages. After file writes, read back the header/row count/a few rows, list source and destinations, and check counts add up, format (columns, delimiter, ordering, path) is exact.
- Build a table of every item in the source list with its status and evidence (e.g. transaction id) and account for each. If the number of actions is surprisingly small or large relative to the source, investigate.
- Check candidates against every constraint (person, status, time, app, genre, owner, direction, exclusions). For newest/oldest/max/min/count questions print the top few candidates with ranking fields, number evaluated per source, items skipped for missing data, and ties; confirm the sort key matches the criterion.
- Treat 0, empty, None, a suspiciously round or surprising result as a pipeline bug, not an answer. Print the raw response, date range, and counts after each filter; relax one filter at a time to find which removes everything. If a fallback branch fired, recheck.
- Confirm the final value has the requested type, format and units (title vs id vs number) and is a real existing value, not a placeholder. Confirm the code ran to the end with no truncated step or swallowed error.
- Do not loosen a check just to make it pass. Never complete on an assumption such as "presumably done".

## Completing the Task

## Completing the Task

- Call `apis.supervisor.complete_task(...)` once, after verification, in its own step, inside an executable ```python code block (a bare statement outside a code block fails with "No code available to execute").
- Question tasks: `complete_task(answer=<value>)` with only the requested value in plain form (a bare number or short string, not a sentence; numbers as numbers), in the requested units. Derive it from printed, observed data. If the task asks for both an action and an answer, derive both from the same variable.
- Action-only tasks: `complete_task()` with no answer. Never submit a count, summary, status or filler such as "done".
- Take every value from API results; never use guessed or placeholder values.
- Never put `complete_task(status="fail")`, `exit` or `raise SystemExit` in exploratory or fallback paths. For missing matches, print, assert or raise to debug and retry with a different approach. Declare failure only when the task is truly impossible after real attempts. Do not complete if a required step failed or was never confirmed. Ask the user via the supervisor only if the information truly cannot be found in the apps.

## Pitfalls

## Pitfalls

- Guessing API names, parameters, response keys, credentials or ids instead of reading docs and printing output.
- Forgetting `print(...)`, or relying on output you have not inspected; long scripts built on unverified assumptions.
- Stopping at the first page, or acting on the first partial match.
- Acting on a whole collection when the task names a subset.
- Passing `access_token` or other undocumented parameters to APIs that do not take them; copying an auth pattern without checking the doc.
- Hardcoding dates or values from memory instead of deriving them from API results.
- Bundling retrieval, mutation and `complete_task` in one cell; making irreversible calls on uncertain matches.
- Assuming empty output means success.
- Submitting an answer on an action-only task, or extra words in an answer.
