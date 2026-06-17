# Troubleshooting

This bot talks to X (Twitter) through [`twikit`](https://github.com/d60/twikit), an
**unofficial** client. Because X changes its internals frequently, `twikit` breaks
periodically — usually in the request-signing logic or the response parsers. This
file records the failure modes we've hit, why they happen, and how they're handled
in the code, so future debugging doesn't start from zero.

> Most X issues fall into one of three buckets: **(1) signing/transaction-id**,
> **(2) Cloudflare blocking**, or **(3) twikit response-parser drift**.

---

## X (Twitter)

### 1. `Client.login() takes 1 positional argument but 4 were given`

- **Cause:** twikit's `login()` is keyword-only — `login(*, auth_info_1, auth_info_2, password, ...)`.
  Passing values positionally fails.
- **Fix:** call with keywords. See `TwitterAdapter.validate_credentials()` →
  `client.login(auth_info_1=..., auth_info_2=..., password=...)`.

### 2. `Couldn't get KEY_BYTE indices`

- **Cause:** Every X API call needs an `X-Client-Transaction-Id`. twikit computes it by
  scraping x.com for the `ondemand.s` script hash. X changed their webpack manifest from
  the inline form `"ondemand.s":"<hash>"` to a two-part mapping
  (`<id>:"ondemand.s"` + a separate `<id>:"<hash>"`), which twikit's regex can't read.
  It also serves a stripped page unless full browser headers are sent.
- **Fix:** `adapters/twitter_patch.py` monkeypatches `ClientTransaction.get_indices` to
  resolve the hash from the new manifest and refetch x.com with browser headers. Applied
  automatically on import of `adapters/twitter.py`.
- **If it returns:** X changed the page again. Re-check `_resolve_ondemand_hash()` in
  `twitter_patch.py` against the current x.com source (look for how `ondemand.s` maps to
  its file hash).

### 3. `403` Cloudflare — _"Sorry, you have been blocked"_

- **Cause:** X's **login** endpoint is Cloudflare-protected and blocks datacenter / VPS /
  hosting IPs (e.g. Aruba, OVH, AWS). The static homepage still loads (so transaction-id
  generation works), but the login flow is refused.
- **Fix:** **Don't use password login on a server.** Use cookie-based auth instead
  (`X_AUTH_TOKEN` + `X_CT0`), which skips the login endpoint entirely. The adapter prefers
  cookies automatically.
- **Still blocked when _posting_ (not logging in)?** Then the API host itself is being
  challenged from your IP — route the bot through a residential/mobile proxy. This is an
  infrastructure problem, not a code one.

### 4. "Tokens are invalid" even though the cookies are fresh

- **Cause:** Usually a **false alarm**. The session check used twikit helpers
  (`user_id()`, `user()`) that are broken against current X: `user_id()` hits a dead
  v1.1 endpoint (`account/settings.json` → 404 code 34), and `user()` crashes in twikit's
  object parser. The cookies were fine; the *probe* was broken.
- **Fix:** `_verify_session()` validates via the raw GraphQL `user_by_screen_name`
  endpoint and checks the returned handle — no broken helpers, no object parsers.
- **Sanity check your cookies:** `auth_token` should be ~40 hex chars, `ct0` ~160 chars,
  with no surrounding quotes or whitespace in `.env`.

### 5. `KeyError: 'urls'` / `NotFound: ... code 34` when reading or posting

- **Cause:** twikit's **response parsers** drift from X's schema. Example: building a
  `User` does `legacy['entities']['description']['urls']`, which `KeyError`s for accounts
  whose bio has no link. The request actually **succeeded** — twikit just chokes parsing it.
  The danger: if this happens on `create_tweet` *after* the tweet posts, the post looks
  like a failure and a retry can **double-post**.
- **Fix:** `_create_tweet_raw()` posts via twikit's raw GraphQL layer
  (`client.gql.create_tweet(...)`) and reads `rest_id` straight from the JSON, bypassing
  the `Tweet` parser. A parser bug can no longer turn a successful post into a "failure".
- **If a read call you rely on breaks the same way:** fetch via `client.gql.<method>()` and
  read the raw dict instead of the high-level wrapper.

### 6. Auth works for weeks, then suddenly fails

- **Cause:** the X `auth_token` cookie expired or was invalidated (e.g. you logged out of
  that browser session, or changed your password).
- **Fix:** re-export `auth_token` + `ct0` from a logged-in browser into `.env`, and delete
  the stale `storage/twitter_cookies.json` so a fresh session is saved.

---

## Cookies & sessions

- `storage/twitter_cookies.json` (X) and `storage/instagram_settings.json` (IG) cache live
  sessions and are **gitignored** — never commit them.
- Deleting a session file forces a fresh login/cookie-load on the next run. Do this whenever
  auth gets into a weird state.

## General

- **Nothing is being cross-posted:** on first run the bot **seeds** state with your latest
  existing post and only mirrors posts created *after* that. Make a new Bluesky post to test.
- **A target is being skipped:** that platform's credentials are missing/empty in `.env`.
  The bot logs `⚠️ ... credentials not found. Skipping` for each disabled target.
- **Verbose logs:** set `LOG_LEVEL=DEBUG` in `.env`.
