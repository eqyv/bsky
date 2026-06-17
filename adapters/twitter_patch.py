# adapters/twitter_patch.py
"""
Compatibility patch for twikit 2.3.3's X (Twitter) client-transaction-id logic.

X changed the format of their webpack manifest. The `ondemand.s` script hash
used to appear inline as `"ondemand.s":"<hash>"`, which twikit's regex expects.
It now appears as a two-part mapping — `<id>:"ondemand.s"` (id -> chunk name)
plus a separate `<id>:"<hash>"` (id -> file hash). twikit can no longer find
the hash, so `ClientTransaction.get_indices` raises:

    Exception: Couldn't get KEY_BYTE indices

…which surfaces on the first API call (login *and* posting). This module
patches `get_indices` to resolve the hash from the new manifest format, and to
re-fetch x.com with full browser headers if the page twikit saw didn't include
the manifest. Idempotent: importing/applying more than once is safe.

This is inherently brittle — if X changes their page again, this may need
updating. Re-check the `ondemand.s` resolution if "KEY_BYTE indices" returns.
"""
import re

from twikit.x_client_transaction.transaction import ClientTransaction, INDICES_REGEX

# Headers that reliably elicit the full homepage (with the webpack manifest).
# twikit's default transaction headers omit Accept / Sec-Fetch-*, and X serves
# a stripped page without the `ondemand.s` reference for those requests.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

# Old inline format: "ondemand.s":"<hash>"
_INLINE_HASH_RE = re.compile(r"""["']ondemand\.s["']\s*:\s*["']([0-9a-f]+)["']""")
# New manifest: <id>:"ondemand.s"
_CHUNK_ID_RE = re.compile(r'(\d+):"ondemand\.s"')


def _resolve_ondemand_hash(page: str):
    """Return the ondemand.s script hash from page source, or None."""
    m = _INLINE_HASH_RE.search(page)
    if m:
        return m.group(1)
    idm = _CHUNK_ID_RE.search(page)
    if idm:
        # Find the same chunk id mapped to a hex hash elsewhere in the manifest.
        for hm in re.finditer(rf'{idm.group(1)}:"([0-9a-f]+)"', page):
            return hm.group(1)
    return None


async def _patched_get_indices(self, home_page_response, session, headers):
    response = self.validate_response(home_page_response) or self.home_page_response
    page = str(response)

    ondemand_hash = _resolve_ondemand_hash(page)
    if not ondemand_hash:
        # Page twikit fetched lacked the manifest — refetch with browser headers.
        r = await session.request(method="GET", url="https://x.com", headers=_BROWSER_HEADERS)
        ondemand_hash = _resolve_ondemand_hash(r.text)
    if not ondemand_hash:
        raise Exception("Couldn't resolve ondemand.s hash (X page format changed?)")

    url = (
        f"https://abs.twimg.com/responsive-web/client-web/"
        f"ondemand.s.{ondemand_hash}a.js"
    )
    js_response = await session.request(method="GET", url=url, headers=_BROWSER_HEADERS)

    indices = [m.group(2) for m in INDICES_REGEX.finditer(js_response.text)]
    if not indices:
        raise Exception("Couldn't get KEY_BYTE indices")
    indices = list(map(int, indices))
    return indices[0], indices[1:]


def apply() -> None:
    """Install the patched get_indices onto twikit's ClientTransaction (idempotent)."""
    if getattr(ClientTransaction, "_crosspost_patched", False):
        return
    ClientTransaction.get_indices = _patched_get_indices
    ClientTransaction._crosspost_patched = True
