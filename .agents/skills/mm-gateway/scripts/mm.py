#!/usr/bin/env python3
"""Client for mm-gateway: read your own Mattermost without holding a Mattermost token.

The gateway holds the Mattermost credential. What this script stores is the
Keycloak refresh token it got from approving the device flow — still a
credential, kept at ~/.config/mm-gateway/tokens.json with 0600.

Standard library only, so it runs anywhere python3 does.
"""
import argparse
import base64
import fcntl
import getpass
import json
import os
import platform
import shutil
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("MM_GATEWAY_URL", "https://mm-gateway.admin.lvtv.me").rstrip("/")
HOME = os.path.expanduser(os.environ.get("MM_GATEWAY_HOME", "~/.config/mm-gateway"))
TOKENS = os.path.join(HOME, "tokens.json")
LOCK = os.path.join(HOME, "lock")

# The gateway release this skill was exported alongside; see TAG in the
# Makefile of the mm-gateway repo, which the export script checks against this.
VERSION = "23"

# The gateway caps both attribution headers at this many bytes and logs what
# fits, so anything longer is sent only to be cut in half there.
MAX_HEADER = 128

# Refresh this far before the access token actually expires, so a slow call
# does not start valid and finish rejected.
EXPIRY_MARGIN = 60
TIMEOUT = 120

# A read is retried while the gateway answers with one of these, or refuses the
# connection outright. The 5xx trio is what a rolling deployment looks like
# from here; 429 is the gateway's own rate limit saying "same request, later".
# All brief, self-resolving, and no reason to fail a whole agent run. Reads
# only — they are GETs, so repeating one costs nothing but a moment.
TRANSIENT_STATUS = frozenset({429, 502, 503, 504})
RETRIES = 2
BACKOFF = 1.0


class Failure(Exception):
    """Anything the caller should be told about in words rather than a stack."""

    # Exit codes exist so a caller can tell the one recoverable failure from
    # every other one without matching on the text of a message. Anything that
    # reads these prose strings breaks the day somebody rewords them.
    exit_code = 1


class NeedsApproval(Failure):
    """The session is gone, and only the human can start another.

    Its own code because this is the one failure with a remedy: run `login` and
    have the human approve. Everything else is either transient or a mistake in
    the request, and re-running the device flow fixes neither.
    """

    exit_code = 2


class Transient(Failure):
    """The gateway did not answer, and might on the next try.

    Kept distinct from NeedsApproval above all: a gateway that is redeploying
    must never read as an expired session, or every agent sends its human back
    through the device flow over a thirty-second outage.
    """


# --- storage ---------------------------------------------------------------


def _ensure_home():
    os.makedirs(HOME, mode=0o700, exist_ok=True)


def load_tokens():
    try:
        with open(TOKENS) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_tokens(tokens):
    """Write atomically: a half-written token file locks the agent out until
    somebody logs in again."""
    _ensure_home()
    tokens = dict(tokens)
    if "expires_in" in tokens:
        tokens["expires_at"] = time.time() + float(tokens["expires_in"])

    temporary = TOKENS + ".tmp"
    with open(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as fh:
        json.dump(tokens, fh)
    os.replace(temporary, TOKENS)
    return tokens


class Lock:
    """Serialises refreshes across concurrent runs.

    Not belt-and-braces. The gateway detects refresh-token replay: whichever of
    two racing runs saves its token second leaves the other's token in the
    file, and presenting that one later reads as a stolen credential and closes
    the session for every agent you have. One at a time.
    """

    def __enter__(self):
        _ensure_home()
        self.handle = open(os.open(LOCK, os.O_WRONLY | os.O_CREAT, 0o600), "w")
        fcntl.flock(self.handle, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_):
        fcntl.flock(self.handle, fcntl.LOCK_UN)
        self.handle.close()
        return False


# --- who this client is ----------------------------------------------------


def _trimmed(value):
    """Cut a header down to what the gateway will record.

    Measured in bytes, because that is the unit the cap there is in, and the
    partial character a byte-slice can leave is dropped rather than sent. The
    gateway strips and truncates these itself — it has to, they arrive from
    strangers — so this is not what makes them safe. It is the difference
    between an identity that lands whole and one that lands cut in half, and,
    for the printable part, between a mistyped MM_CLIENT_ID and a client that
    cannot make a request at all: urllib refuses to send a header value with a
    line ending in it, so an unfiltered one would fail every command rather
    than merely log oddly.
    """
    printable = "".join(char for char in value if char.isprintable())

    return printable.encode()[:MAX_HEADER].decode(errors="ignore")


def _known_identity():
    """The name this client last authenticated under, if it ever has.

    Read out of the access token already sitting in the token file: its payload
    only, with nothing verified and no signature checked. That is not a
    shortcut — it is the point. This produces a label for somebody else's log
    line, never a decision, and the gateway treats what we send as a claim from
    a stranger no matter how we arrived at it. Verifying it here would buy
    nothing and would suggest it means more than it does.

    Worth the trouble for one case above all. A `login` that polls for
    thirty-five minutes is almost never a first login — it is a session that
    expired, so the file is still there with the previous session's token in
    it, and that token knows the name of the person whose script is looping.
    Marked `sso:` because it is the Keycloak username, which is the field the
    gateway's own log lines carry and therefore the one worth joining against;
    the local account name below is a guess at a person, and this is not.

    The one run that cannot be named this way is a genuinely first approval,
    and nothing else could name that one either.
    """
    try:
        payload = load_tokens().get("access_token", "").split(".")[1]
        claims = json.loads(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        name = claims.get("preferred_username") or claims.get("sub") or ""
    except Exception:
        # A token file that is absent, empty, half-written, opaque rather than
        # a JWT, or holding a shape nobody expected. Every one of those means
        # the same thing here: fall back and say so, rather than fail a command
        # over a field that only decorates a log line.
        return ""

    return f"sso:{name}" if name else ""


def _self_description():
    """Name this run: the script, its version, who ran it and where.

    Best effort throughout. getpass.getuser() consults the environment and then
    the password database, and in a container both can be missing; a client
    that cannot work out its own name still has requests to make, and an
    unknown half is worth more than no header.
    """
    who = _known_identity()
    if not who:
        try:
            who = getpass.getuser()
        except Exception:
            who = "unknown"

    try:
        host = socket.gethostname() or "unknown"
    except OSError:
        host = "unknown"

    return f"mm.py/{VERSION} {who}@{host}"


# What this client volunteers about itself on every request. Nothing verifies
# it and nothing about the answer depends on it: it is there so that a request
# carrying no credential is still attributable. `login` polls for an approval
# only a human can give, and until they give it every one of those requests is
# anonymous — and from behind the corporate VPN they all share one source
# address, so without this the gateway's log has nothing to say whose script is
# looping.
#
# Settled once per run rather than per request, so every line one process
# produces files under the same name even if it refreshes a token halfway
# through.
#
# MM_CLIENT_ID overrides it, which is how a scheduled job or a shared machine
# says what it is instead of naming whichever account it happens to run as.
CLIENT_ID = _trimmed(os.environ.get("MM_CLIENT_ID") or _self_description())
USER_AGENT = _trimmed(f"mm.py/{VERSION} (python {platform.python_version()})")


def _headers(extra=None):
    """The headers every request carries, plus whatever this one needs.

    urllib title-cases what it is given, so `X-Client-Id` goes out as
    `X-client-id`. Header names are case-insensitive and the gateway reads it
    either way; it is worth knowing before searching a packet capture for the
    spelling used here.
    """
    headers = {"User-Agent": USER_AGENT, "X-Client-Id": CLIENT_ID}
    if extra:
        headers.update(extra)

    return headers


# --- transport -------------------------------------------------------------


def _request(req):
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"error": "http_error", "error_description": raw[:400]}
    except urllib.error.URLError as exc:
        raise Transient(f"cannot reach {BASE}: {exc.reason}") from exc


def post_form(path, fields):
    body = urllib.parse.urlencode(fields).encode()
    return _request(urllib.request.Request(
        BASE + path, data=body,
        headers=_headers({"Content-Type": "application/x-www-form-urlencoded"})))


def get(path, access):
    return _request(urllib.request.Request(
        BASE + path, headers=_headers({"Authorization": "Bearer " + access})))


def _stream(path, access, destination):
    """Fetch one file to disk. Returns (status, error body) and writes nothing
    unless the gateway answered with the file."""
    req = urllib.request.Request(
        BASE + path, headers=_headers({"Authorization": "Bearer " + access}))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            with open(os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as out:
                shutil.copyfileobj(resp, out)
            return resp.status, None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"error": "http_error", "error_description": raw[:400]}
    except urllib.error.URLError as exc:
        raise Transient(f"cannot reach {BASE}: {exc.reason}") from exc


# --- authorization ---------------------------------------------------------


def login(_args):
    """Device flow. The human approves in a browser; this waits for them."""
    status, grant = post_form("/v1/auth/device_authorization", {})
    if status != 200:
        raise Failure(f"could not start the device flow: {describe(grant)}")

    url = grant.get("verification_uri_complete") or grant["verification_uri"]
    print("Open this and approve:\n", file=sys.stderr)
    print(f"  {url}", file=sys.stderr)
    print(f"  code: {grant['user_code']}\n", file=sys.stderr)
    print("Waiting for approval…", file=sys.stderr)

    interval = int(grant.get("interval", 5))
    deadline = time.time() + int(grant.get("expires_in", 600))

    while time.time() < deadline:
        time.sleep(interval)
        status, token = post_form("/v1/auth/token", {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": grant["device_code"],
        })
        if status == 200:
            save_tokens(token)
            print("Approved. The session lasts a week.", file=sys.stderr)
            return {"status": "approved"}

        code = token.get("error")
        if code == "authorization_pending":
            continue
        if code == "slow_down":
            interval += 5
            continue

        raise Failure(f"authorization failed: {describe(token)}")

    # Deliberately not NeedsApproval: that code tells a caller to run this
    # command, and this is that command. A human who did not approve in ten
    # minutes is not going to be helped by an agent starting the flow again.
    raise Failure("the code expired before it was approved; run login again")


def refresh(tokens):
    status, fresh = post_form("/v1/auth/token", {
        "grant_type": "refresh_token",
        "refresh_token": tokens.get("refresh_token", ""),
    })
    # A gateway that is down is not a session that is over, and the difference
    # is not cosmetic: the second reading sends the human back through the
    # device flow, and a redeploy would do it to everybody at once. Only the
    # gateway's own refusal of the token ends a session. A 429 is the same
    # shape of not-over: the gateway is rate limiting this address, and the
    # token it refused to look at is still good.
    if status == 429 or status >= 500:
        raise Transient(f"the gateway could not refresh the session ({describe(fresh)})")

    if status != 200:
        raise NeedsApproval(
            f"the session is over ({describe(fresh)}). Run: mm.py login")

    return save_tokens(fresh)


def access_token():
    """Return a usable access token, refreshing under a lock if needed."""
    tokens = load_tokens()
    if not tokens.get("refresh_token"):
        raise NeedsApproval("not authorized yet. Run: mm.py login")

    if tokens.get("access_token") and time.time() < tokens.get("expires_at", 0) - EXPIRY_MARGIN:
        return tokens["access_token"]

    with Lock():
        # Somebody else may have refreshed while we waited for the lock.
        tokens = load_tokens()
        if tokens.get("access_token") and time.time() < tokens.get("expires_at", 0) - EXPIRY_MARGIN:
            return tokens["access_token"]

        return refresh(tokens)["access_token"]


def call(path):
    """One read, retrying once if the access token turns out to be stale.

    The token retry and the transient one are deliberately separate. A 401 is
    answered by refreshing, which must happen once and under the lock; a 502 is
    answered by waiting, which must not refresh anything. Conflating them would
    have a brief outage rotate the refresh token repeatedly for no reason.
    """
    status, body = attempt(path, access_token())
    if status == 401:
        with Lock():
            fresh = refresh(load_tokens())
        status, body = attempt(path, fresh["access_token"])

    if status != 200:
        raise Failure(f"{path} → {status}: {describe(body)}")

    return body


def attempt(path, token):
    """One read, repeated while the gateway is briefly unable to answer.

    The last attempt returns its transient status rather than swallowing it, so
    a gateway that stays down is reported as what it answered instead of as a
    generic timeout.
    """
    for remaining in range(RETRIES, -1, -1):
        try:
            status, body = get(path, token)
            if status not in TRANSIENT_STATUS or not remaining:
                return status, body
        except Transient:
            if not remaining:
                raise

        time.sleep(BACKOFF * (RETRIES - remaining + 1))

    raise Transient(f"{path}: no answer after {RETRIES + 1} attempts")


def describe(body):
    if isinstance(body, dict):
        return body.get("error_description") or body.get("error") or json.dumps(body)[:200]
    return str(body)[:200]


# --- reads -----------------------------------------------------------------


def query(**params):
    # Unset, off, and blank are dropped; zero is not. `0 == False` in Python,
    # so testing membership in a tuple of falsy values silently swallowed
    # --limit 0 — which the gateway refuses by name, and which the caller was
    # entitled to be told about rather than answered with a full listing.
    live = {k: v for k, v in params.items() if v is not None and v is not False and v != ""}
    return ("?" + urllib.parse.urlencode(live)) if live else ""


def channels(args):
    # "with" is a keyword, so argparse holds it as with_; the wire name is not.
    params = {
        "limit": args.limit, "active_since": args.active_since,
        "kind": args.kind, "unread": args.unread and "true", "with": args.with_,
        "name": args.name,
    }

    return call("/v1/channels" + query(**params))


def search(args):
    return call("/v1/search" + query(q=args.query, limit=args.limit, page=args.page))


def threads(args):
    return call("/v1/threads" + query(
        limit=args.limit, unread=args.unread and "true", since=args.since))


def saved(args):
    return call("/v1/saved" + query(limit=args.limit, page=args.page))


def messages(args):
    return call(f"/v1/channels/{args.channel}/messages" + query(
        limit=args.limit, before=args.before, after=args.after, since=args.since))


def thread(args):
    return call(f"/v1/messages/{args.message}/thread" + query(limit=args.limit))


def pinned(args):
    return call(f"/v1/channels/{args.channel}/pinned")


def files(args):
    return call("/v1/files" + query(q=args.query, limit=args.limit, page=args.page))


def file_(args):
    """Fetch one attachment, or mint a link to it.

    Two different jobs because they are for two different readers. The bytes are
    for you: you were asked what is in something and you have to open it. The
    link is for a person, and it works in a browser that is signed in to nothing
    — which is the ordinary case, since people read Mattermost in its own app.

    A stale access token is retried once, exactly as a read is. A transient
    failure is not: every other call here is a GET of some JSON, and repeating
    one costs a moment, while repeating this one means writing over a file it
    already half wrote.
    """
    if args.link:
        return call(f"/v1/files/{args.file}/link")

    destination = args.output or args.file
    # Refused rather than overwritten: the default destination is a name
    # somebody else chose when they attached the file, and silently writing over
    # whatever already goes by that name here is not a thing to do quietly.
    if os.path.exists(destination) and not args.force:
        raise Failure(f"{destination} already exists; pass --output or --force")

    status, failure = _stream(f"/v1/files/{args.file}", access_token(), destination)
    if status == 401:
        with Lock():
            fresh = refresh(load_tokens())
        status, failure = _stream(f"/v1/files/{args.file}", fresh["access_token"], destination)

    if status != 200:
        raise Failure(f"file {args.file} → {status}: {describe(failure)}")

    return {"path": destination, "size": os.path.getsize(destination)}


def whoami(_args):
    return call("/v1/me")


# --- entry point -----------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        prog="mm.py", description="Read your own Mattermost through mm-gateway.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="approve a new session (once a week)").set_defaults(run=login)
    sub.add_parser("whoami", help="the account this maps to").set_defaults(run=whoami)

    listing = sub.add_parser("channels", help="your conversations, most recent first")
    listing.add_argument("--limit", type=int)
    listing.add_argument("--active-since", help="7d, 48h, 30m, or an RFC 3339 timestamp")
    listing.add_argument("--kind", help="public, private, direct, group (comma-separated)")
    listing.add_argument("--unread", action="store_true", help="only what you have not read")
    listing.add_argument("--with", dest="with_", metavar="PERSON",
                         help="email, @username, or part of a name")
    listing.add_argument("--name", metavar="CHANNEL",
                         help="a channel's slug or display name; the way to get its id")
    listing.set_defaults(run=channels)

    finder = sub.add_parser("search", help="find messages across everything you can see")
    finder.add_argument("query", help="mattermost search syntax: in:slug from:user \"phrase\" -not")
    finder.add_argument("--limit", type=int)
    finder.add_argument("--page", type=int)
    finder.set_defaults(run=search)

    following = sub.add_parser("threads", help="threads you follow")
    following.add_argument("--limit", type=int)
    following.add_argument("--unread", action="store_true")
    following.add_argument("--since", help="RFC 3339 timestamp")
    following.set_defaults(run=threads)

    marks = sub.add_parser("saved", help="messages you bookmarked")
    marks.add_argument("--limit", type=int)
    marks.add_argument("--page", type=int)
    marks.set_defaults(run=saved)

    history = sub.add_parser("messages", help="one conversation's history, oldest first")
    history.add_argument("channel")
    history.add_argument("--limit", type=int)
    history.add_argument("--before", help="message id from a previous response's `older`")
    history.add_argument("--after", help="message id from a previous response's `newer`")
    history.add_argument("--since", help="RFC 3339 timestamp")
    history.set_defaults(run=messages)

    replies = sub.add_parser("thread", help="a message and its replies")
    replies.add_argument("message")
    replies.add_argument("--limit", type=int)
    replies.set_defaults(run=thread)

    marked = sub.add_parser("pinned", help="messages pinned in one conversation")
    marked.add_argument("channel")
    marked.set_defaults(run=pinned)

    attachments = sub.add_parser("files", help="find attachments across everything you can see")
    attachments.add_argument("query", help="file search syntax: ext:pdf in:slug from:user \"phrase\"")
    attachments.add_argument("--limit", type=int)
    attachments.add_argument("--page", type=int)
    attachments.set_defaults(run=files)

    one = sub.add_parser("file", help="fetch one attachment, or mint a link to give somebody")
    one.add_argument("file", metavar="FILE_ID", help="an id from a message's files[]")
    one.add_argument("-o", "--output", metavar="PATH",
                     help="where to write it; defaults to the file id in the current directory")
    one.add_argument("--force", action="store_true", help="overwrite the destination if it exists")
    one.add_argument("--link", action="store_true",
                     help="mint a short-lived URL for a person instead of fetching the bytes")
    one.set_defaults(run=file_)

    return parser


def main():
    args = build_parser().parse_args()
    try:
        result = args.run(args)
    except Failure as failure:
        print(f"error: {failure}", file=sys.stderr)
        return failure.exit_code

    json.dump(result, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
