## Workflow

## Workflow

1. Read the task literally and list every requirement: apps, action, target set, every qualifier (who, which items, status, type, "so far", "only", month AND year, direction sent vs received), counts, recipients, destinations, the "all others" fallback, and the output format. Classify it as a **question** task (returns a value) or an **action-only** task (follow, like, send, add, delete, update, write a file). Never swap a stated verb for its opposite. Turn each qualifier into an explicit filter in code. When two collections are named (e.g. "in my library AND liked"), fetch both and intersect them.
2. Discover APIs read-only first: `apis.api_docs.show_app_descriptions()`, `apis.api_docs.show_api_descriptions(app_name=...)` (list ALL of an app's APIs before choosing; print in pieces if truncated), then `apis.api_docs.show_api_doc(app_name=..., api_name=...)` before the first use of EVERY API, including login, detail and delete endpoints. Note exact parameter names, required parameters, auth needs, enum values, pagination parameters, and the response schema.
3. Match the API to the task verb and concept. "Request money" is the payment-request API, not send-money. "Liked", "starred", "following" and "owned" map to dedicated endpoints, not to side fields such as counts. A wrong direction or record type fails the task even if the code runs.
4. Authenticate (see Authentication).
5. Work in small, complete REPL steps, one phase per step: fetch, print, filter, print the filtered set, preview, act, verify. Always `print(...)` what you need to see (bare expressions are not echoed; "Execution successful" with no output proves nothing). Keep variables between steps; if a NameError shows state was lost, re-fetch and recompute. Only standard Python libraries are available. Use app APIs for files rather than `os` or `io`.
6. Keep code blocks short and syntactically complete. A truncated block can report success while doing nothing.
7. Do the actual actions for every sub-step; do not stop after exploring. Then verify and complete (see Verification and Completing the Task).

## Authentication

## Authentication

- Get credentials from `apis.supervisor.show_account_passwords()` (use the entry for the target app) and the user's own details from `apis.supervisor.show_profile()` (also `show_addresses()`, `show_payment_cards()` when needed). Never guess or invent credentials.
- Read each app's `login` doc to see what `username` expects; it differs per app (email for some, phone number for others). Log in to every app whose APIs need an `access_token` (including file_system and phone). If login fails with invalid credentials (401), try the other identifier before blaming the password.
- Print the login result, store each token in a named variable, and pass `access_token` only to APIs whose docs list it. An "Unexpected parameter" error means remove the argument; a later 401 usually means a missing or wrong token.

## API Usage and Schema Rules

## API Usage and Schema Rules

- Never guess API names, parameters, IDs, enum values or response keys. Before writing logic that depends on a field, read the documented schema and print one real response object (`type(x)`, `obj.keys()`, or `json.dumps(obj, indent=2)[:1500]`). Use the exact key names (e.g. `id` vs `message_id`). Pass all required parameters and no unlisted ones. Omit optional parameters you do not need instead of passing None or placeholders.
- Prefer direct indexing (`obj["key"]`) or asserts over `.get(k, default)`, `or []`, `.get(a) or .get(b)` chains, so a wrong key fails loudly. Do not wrap logic in bare `try/except: continue` or silent guards such as `if not value: continue`. If a lookup is None, empty or missing, stop, print the raw record and re-read the docs. Never silently skip items; count and print what was skipped and why.
- On an API error, read the full message (it often lists allowed parameters or enum values) and that API's doc, then fix the root cause. Do not repeat the same call unchanged or try random alternatives. A 409 "already exists" on create means find the existing record and update it.
- List endpoints often return summaries without dates, durations, genres, prices or ratings. Use the entity's own `show_*` detail endpoint for its own attributes (cache per id). Check first whether the list already embeds nested data. Do not substitute a parent's or related object's attribute unless the docs confirm they are equivalent.
- Create, update, list and show variants each have their own signature; check each. In update calls pass only the fields that change.
- Check units (seconds vs minutes, cents vs dollars) in the schema. Sum or compare in raw units; convert or round once on the final value.
- Output may be truncated. Never conclude from a cut-off printout; print compact summaries (counts, `collections.Counter`, distinct values, only needed fields).
- Treat an unexpectedly empty, zero or None result as a pipeline bug (wrong field, type, case, direction, pagination), not as an answer. Look in the docs for flags that fold several steps into one call (e.g. a delete-original option on compress).

## Pagination and Data Collection

## Pagination and Data Collection

- Treat every list, search and library endpoint as paginated. Read the doc for `page_index` (start value), `page_limit`, defaults and maximums. Pass `page_limit` explicitly (use the max) and loop over `page_index` until a page is empty or shorter than the limit. Never count, rank, act on or answer from only the first page. Print the total collected.
```python
def fetch_all(fn, page_limit=20, **kw):
    out, i = [], 0
    while True:
        page = fn(page_index=i, page_limit=page_limit, **kw)
        if not page:
            break
        out.extend(page)
        if len(page) < page_limit:
            break
        i += 1
    return out
```
- Adjust the start index and limit to the doc. Do not modify items while paginating, since pages shift; collect IDs first, then act.
- Fully retrieve reference lists (contacts, friends, playlists, transactions, feeds) before using them as filters.
- Cover every source and container the task mentions (library, albums, playlists, notes, multiple accounts), and process each on its own using each item's own attributes. Print the count each source contributes and check none is unexpectedly zero.
- Ownership: when a list contains other users' records, filter to the current user's by a verified field (email or id). Never assume index 0 is yours. Do not modify records that are not yours.
- If the docs offer server-side `sort_by` (e.g. `-field`), filters or search parameters, you may use them for most/top/latest/oldest requests, then sanity-check the result. Otherwise paginate fully and aggregate in code.

## Search, Filtering and Ranking

## Search, Filtering and Ranking

- Map each criterion to a dedicated API parameter when one exists (genre, sender, user, direction, relationship, min/max counts, dates, sort order). Prefer structured filters over free-text `query`, which matches names and other fields and returns wrong items. Then confirm in code that each returned item satisfies every criterion.
- For categorical values, look up the exact label first (a genres helper, distinct values in printed data) and normalize case and whitespace. Check all variants of a category. Do not assume casing or format.
- Check filter semantics (inclusive vs exclusive thresholds, "at least" vs "more than"). When the API filter is uncertain, filter client-side. Parse dates and numbers before comparing; do not compare loose strings.
- If a search returns empty, retry with other terms, synonyms or filters (e.g. a relationship filter instead of an empty query) before concluding data is missing.
- After searching, print the candidates with the fields used for filtering. Filter by the criteria first, keeping structured attributes (genre, date, rating) until after filtering, then reduce to the output format. Respect the requested order, separator and header names.
- Translate scope qualifiers ("so far", "up to and including the current", "before", "latest", "unread", "only certain senders") into explicit filters. For position-based qualifiers, find the boundary marker (current-item API, index, played flag) and include or exclude the boundary item as the wording says. "All pending" or "everything" is not the scope when a subset is named.
- For user-scoped wording ("my", "favorite", "most listened", "in my library"), scan the full API list for user-specific variants (`*_privates`, library, liked, history, stats) and read their docs before using public aggregate fields such as global play counts.
- For superlatives (most/least/latest/top-N), collect all candidates from all required sources, get the needed metric via detail calls if missing, print every candidate with its metric, pick the extremum from the printed values in code (`Counter`, `sum`, `max`, `sorted`), and check ties. When an item has several sub-entities (a song with several artists), count each one. Match the aggregation to the wording (sum vs net, owned vs liked, all vs some).

## Resolving Entities, People and Status

## Resolving Entities, People and Status

- Never blindly take `results[0]`. Print name/title and key fields of all results, open the candidates, and choose the exact match for the requested name, owner or container. Handle duplicates and near matches explicitly. Confirm membership in a container (album, playlist, folder) through the data's membership field. Print the full mapping from each source name to its resolved id, email or phone number, show misses, and investigate each one (other search terms, other apps, other fields). Decide what a name is from context (artist vs user vs contact) and try the other plausible lookups before concluding it is absent.
- Map relational words (coworker, family, roommate, friend, manager) to real data, never to a proxy. Phone contacts with relationship fields (e.g. `apis.phone.search_contacts(relationship=..., page_index=...)`) are the primary definition; app-specific friend lists are only a cross-check. Note list-typed fields (e.g. `relationships`) versus strings.
- Match people across apps by a stable field (email or phone) with normalized case and whitespace, not display names alone; print a few raw entries to see which fields are populated, print unmatched people, and use the target app's user search when needed.
- Contradictory signals (empty child lists, failed lookups, unexpected counts) mean you probably picked the wrong entity; recheck before working around it. If a key value (duration, amount, date, recipient) is missing, you probably have the wrong source; keep searching and never reinterpret an unrelated field.
- Decide status (paid, done, already exists) from scoped evidence: counterparty AND amount AND purpose (note/description) AND date window. Mere presence in history is not proof. List the actual records with dates, amounts and notes; treat mismatched or partial amounts as unsettled. If one source lacks the record, fall back to a related source that records the outcome (e.g. transaction history instead of a request list).
- When several records plausibly match (notes, files, emails, playlists, transactions), compare each one's date and details with the task's time reference and pick the single best match. Never sum or merge values across candidates without evidence they describe one event.
- When asked to repeat, reverse or refund something, reuse the amount, recipient and description from the original record. Compute shares explicitly (total divided by number of people, including or excluding the user as the task states), and check rounding and currency format.

## Requests From Other People and Missing Targets

## Requests From Other People and Missing Targets

- When a task says to act "as per their request" or "as they asked", FIRST find and read the original message in the relevant channel (text messages, email, chat, notes): search, then open the full message. Do this before gathering data or replying. Extract every constraint (category, creator, date, count, format, recipient) and apply it as a filter. Act only on matching items, never on the whole data set.
- A request to move, update, delete or change something implies it already exists. If a literal keyword search finds nothing, DO NOT create a new record. Re-examine existing items and match by time, label, repeat pattern, owner or date; the task wording may describe the item's purpose, not its exact label. An item the user mentions may be a line inside a larger note or checklist; search by theme or tags and open the likely container. Create new records only when the task explicitly asks.
- If several candidates fit, compare them in printed data and pick the best match by the stated criteria; do not change all of them unless told. Derive new values (times, dates, amounts) from the existing item's actual values.
- Do not trust the task's description of layouts, names or contents (folders, playlists, alarms). List or search first, and go one level deeper if it looks different. Never fabricate paths or names.
- Honor every component of a rule. The "all the others" category is real and applies only to items failing every specific rule. If a category the task implies comes out empty, suspect a bug and recheck.

## Dates and Relative Time

## Dates and Relative Time

- Never hardcode or assume the current date or year. Resolve "today", "yesterday", "last week", "this month", "this year" from an in-environment source: the phone/supervisor date-time API (e.g. `apis.phone.get_current_date_and_time()`, check the docs) or the newest timestamps in app data. Cross-check against `datetime.now()`; if they disagree (e.g. a different year), trust the app data. Print the raw result, parse it with the format actually shown, and use the derived reference date consistently.
- Print a few item timestamps to confirm format and timezone (UTC vs naive) and the date range of the records before comparing.
- Compute relative ranges in code with `datetime` (`strptime`, `timedelta`, `strftime`) giving explicit start and end boundaries. For "N days including today" use min = today - (N-1) days, max = today. Format as the API expects (e.g. YYYY-MM-DD), check whether bounds are inclusive, and filter on the right timestamp field (dates inside records over filenames).
- For "month X of this year", compare both year and month; keep the full timestamp. Fetch over a generous range, then filter in Python, because a narrow API date filter can miss records. Print records just inside and outside the boundaries. If data does not match the expected period, re-examine your interpretation instead of silently substituting another year or month. Do not pick the "latest" item by filename sort.

## Parsing Files, Notes and Messages

## Parsing Files, Notes and Messages

- Before writing a regex or parser, print one or two complete raw samples in a separate step. Never use a generic "first number" regex, since dates, ids, account numbers and years look like numbers. Anchor extraction on labels seen in the sample (e.g. a Total or Amount line), print per-item extracted values, and compare with the raw text.
- Read the full note, message or file the task refers to, parse all its items, count them, and check each was handled. Read the title and content for conventions (e.g. a legend such as `[x]` done) and follow that exact format.
- If the same record exists in several formats (.txt and .pdf), use one readable copy per record to avoid double counting. Check the file_system docs for how to read content and confirm the returned type.
- Derive names and paths from observed output (strip trailing `/`, take the last path component, check `~` prefixes), keep original filenames unless told otherwise, and exclude non-targets such as the output folder itself. Create destination directories first (`recursive=True`) and use `move_file` for "move".
- After filtering by name, date or category, list the matched items and confirm they are exactly the intended set, using precise matching (e.g. the year in a date field) rather than loose substrings.
- Editing existing content: search/list APIs often return metadata only, so call `show_*` for the full content. Update APIs usually replace everything, so do read-modify-write: fetch, change only the target line (match the whole line so similar lines stay untouched), write back the rest unchanged including existing title and tags, then re-fetch and confirm only the intended change occurred.
- When merging several sources, collect from each first and note per-source counts, then deduplicate. Define "unique" on the fields that appear in the output (e.g. title plus set of artist names), not just internal ids. Format multi-valued fields exactly as specified and print the final list before writing it. After writing a file, read it back (e.g. `show_file`) and check header, row count and sample rows.

## Bulk and State-Changing Actions

## Bulk and State-Changing Actions

Applies to send, post, pay, like, follow, add, update, move, delete, unfollow, cancel. Deletes, payments and sent messages cannot be undone.

1. Separate read steps from write steps. Never combine fetching, filtering and mutating in one blind script.
2. Dry-run first: collect the full target set across all pages and containers, deduplicate by id, and print the count and each item with the evidence for choosing it (person, amount, date, matching reason, act/skip decision). Check boundary cases (empty lists, items matching several conditions). If the number of actions is surprisingly small or large relative to the source list, investigate. For bulk moves/deletes, also print a summary of the deciding attributes and a planned item -> destination list.
3. Check the current state first (already followed, liked, paid, existing file) and skip redundant actions. Check balance or funds before sending money; add a payment method only if the task permits. Use exact amounts and recipients found in the data.
4. For messages, emails and payments, build the payload in a variable, print it, check it against the request, and pass that same variable to the call. Never retype computed content by hand.
5. Execute in a separate step. Test one call before looping. Print each item and each write response, and inspect it for error text (a `message` key is not necessarily success); count real successes. In loops, catch only the specific expected error (an "already done" error counts as success) and log or re-raise everything else. Handle every item type the task names separately (e.g. text and voice messages have separate APIs and id fields).
6. After an exception, re-fetch state to see what a partial run applied BEFORE retrying. Never rerun a whole script containing side effects, and never act on variables left over from an errored script; rebuild and print them. Perform each action once.
7. Do only what the task asks: no extra messages, transactions, likes, or collateral deleting. For "delete all except Y" or "keep only A and B", build full id sets and act on the difference (`all - (A & B)`). Stage work: create outputs first and verify they exist at the exact paths, and run destructive steps (account, file or playlist deletion) in a later step only after earlier deliverables are verified. Avoid blanket flags like `delete_directory=True` or `overwrite=True` on unverified data. Do not bundle writes, destructive calls and `complete_task` in one script.

## Verification and Completing the Task

## Verification and Completing the Task

- After writes, re-fetch the affected state with a read API and confirm it matches the intended set exactly (right items, values, recipients, amounts, counts before and after; nothing extra, missing, duplicated or outside the task). A write call's success message or "Execution successful" is not verification. A "0 remaining" check counts only if it covered all items; never weaken a check to make it pass.
- For computed answers, print the itemized records behind the aggregate (counterparty, date, amount, direction, status) and the running total or count. Confirm the scope is right (period, no duplicates, none missing, all required sources included) and that the magnitude is plausible; if implausible, re-inspect.
- Investigate any earlier None, empty or error result before trusting the answer. If output was missing or truncated, rerun in smaller pieces. Make sure every code block was complete and ran.
- Re-read the task and check each requirement and constraint (time range, count, ownership, account, format, units) one by one. If a fallback was used and the requirement is unmet, search further.
- Call `apis.supervisor.complete_task(...)` once, in its own final step inside a real ```python block, only after all actions are done and verified.
- Question task: `complete_task(answer=...)` with only the requested value, derived from inspected data, as a bare value in the requested form (a number as a number, a name or short string; no sentence or extra words). Print it and confirm it matches the question first. Never pass None or a placeholder, or the id of something created by mistake.
- Action-only task: call `apis.supervisor.complete_task()` with NO answer. Do not pass counts, titles, ids, summaries, "done" or status text. Decide this before writing the final call.
- Never call `complete_task` with a fail status, `exit` or `raise SystemExit` from exploratory code or as a fallback for a failed parse. Debug instead; mark failure only after genuinely exhausting reasonable approaches.

## Common Pitfalls

## Common Pitfalls

- Guess-and-retry on API names, parameters, response fields or id names; repeated errors mean the docs were skipped, so re-read that API's doc.
- Picking the wrong API for the task verb, the wrong record type, or the wrong direction.
- Skipping pagination, using only the first page, or ignoring scope words and the year in date rules.
- Using a proxy for a relationship, the first unvalidated search hit, or the system clock alone for the current date.
- Assuming the whole data source is wanted instead of checking the request for filters, or dropping per-item metadata before filtering.
- Double counting duplicate formats or mixing in out-of-range records.
- Fabricating a new record when a search comes back empty, or inventing values instead of fetching them from the apps.
- Blind bulk actions without a preview, long multi-phase scripts that may be truncated or fail midway after irreversible writes, and rerunning scripts that already performed side effects.
- Treating a degenerate result (0, empty, None) as the answer, or completing before verifying.
- Returning a sentence when a single value was requested, or reporting a count or message for an action-only task.
