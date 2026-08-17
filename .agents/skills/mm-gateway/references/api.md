# mm-gateway reference

Detail behind [SKILL.md](../SKILL.md). Read this when you need the search
syntax, the exact response shapes, or to page through something.

## Search syntax

`search` passes Mattermost's own syntax through untouched. Every term must
match; there is no OR.

| | |
| --- | --- |
| `in:slug` | one conversation. **The slug, not the display name** — see below |
| `from:username` | one author. Usernames are what the responses report, so these work as read |
| `before:2026-08-01` `after:` `on:` | dates, `YYYY-MM-DD` |
| `"exact phrase"` | quoted |
| `-word` | exclude |
| `deploy*` | trailing wildcard |
| `#hashtag` | hashtags |

Combine freely: `search 'in:infra-issues from:ak "rollout" -draft after:2026-07-01'`.

### The `in:` trap, in full

Mattermost resolves `in:<name>` to a channel id *before* searching, matching a
channel's `Name` — its URL slug — exactly. It never looks at the display name.
A name that resolves to nothing is not an error: the filter is dropped and you
get an empty result set that looks exactly like "nobody ever discussed this".

Every conversation in a listing or a search result carries both:

```json
{"id":"eqe1…","kind":"private","name":"infra-alerts","slug":"infra-alerts"}
{"id":"6xk2…","kind":"public","name":"Добро пожаловать!","slug":"town-square"}
```

Take `slug` for `in:`. For a direct message the slug is an opaque pair of user
ids — unreadable, and correct.

Searching a conversation you know by name: list first, take the slug, then
search.

## Response shapes

### `channels`

```json
{"channels":[{"id":"…","kind":"direct","name":"Vera P","slug":"…__…",
  "team":"LT","members":[{"id":"…","username":"vp","name":"Vera P"}],
  "last_post_at":"2026-08-12T09:31:04Z","unread":12,"mentions":1}],
 "total":37}
```

- `total` is how many matched **before** `--limit`. If it exceeds the number
  returned, you are looking at a truncated page.
- `unread` and `mentions` appear only with `--unread`. Their absence means
  nobody counted, not that there is nothing.
- `members` is populated for direct and group messages only — those are the
  conversations whose identity is who is in them.
- `name` for a direct or group message is built from the participants, because
  Mattermost does not store one.
- `--name` matches a channel's `slug` or its `name`, case-insensitively, with
  or without a leading `#`. Exact wins; substring matches come back only when
  nothing matched outright, so `infra` answers with `infra` rather than with
  every channel starting `infra-`. It never returns direct or group messages —
  those have no name anybody chose — and combining it with `--with` is a 400,
  because the two select disjoint sets and would always answer with nothing.

### `search` and `saved`

```json
{"messages":[{"id":"…","channel_id":"…","author":{"username":"vp","name":"Vera P"},
  "message":"…","created_at":"2026-08-12T09:31:04Z"}],
 "channels":{"…":{"kind":"direct","name":"Vera P","slug":"…"}}}
```

Newest first. Conversations are named once each under `channels`, keyed by
`channel_id`, rather than repeated on every message — look them up there.

`search` takes `--page` (0–100) for more. `saved` too. Past that it is refused:
paging that deep is an offset upstream, and nothing you actually want is there.

### `messages` and `thread` and `pinned`

```json
{"messages":[…],"older":"<message id>","newer":"<message id>"}
```

**Oldest first**, unlike search — but that describes the order *within* the
page, not which page you get. With no cursor you get the **newest** `--limit`
messages, sorted oldest-first among themselves. So `--limit 3` is the last
three things said, and reading a page of 60 to keep the last three costs
twenty times what it needs to.

`older` and `newer` are cursors: pass `older` back as `--before` for the
previous page, `newer` as `--after` for the next. Either being absent means
there is nothing further that way. `--since` returns everything after a
timestamp and produces no cursors.

`thread` and `pinned` return no cursors.

### Permalinks

A link copied from the Mattermost UI looks like
`https://mm.lvtv.me/<team>/pl/<message id>`. The trailing segment is a message
id: pass it to `thread` to read that message with its replies (or to
`messages --before`/`--after` as a cursor). No unwrapping step exists or is
needed — the id works as is.

### `threads`

```json
{"threads":[{"id":"<root message id>","channel_id":"…","root":{…message…},
  "replies":20,"unread_replies":3,"unread_mentions":1,
  "last_reply_at":"…","participants":[{"username":"vp","name":"Vera P"}]}],
 "channels":{…}}
```

Most recently replied to first. The `root` is a full message. **The replies are
not here** — fetch them with `thread <id>`, using the thread's `id`, which is
the root message's id.

**A root here never carries `reactions` or `files`**, however many the message
actually has — Mattermost answers a thread listing from its own store instead
of preparing each post the way every other route does, and both fields ride on
the metadata that preparation adds. So an absent `reactions` here means nothing
either way, unlike everywhere else on this surface. Read `thread <id>` before
concluding nobody reacted.

No `total`: threads arrive one page at a time, so any total would be the page's
own size wearing a bigger name. A full page means there may be more.

### Messages

```json
{"id":"…","channel_id":"…","thread_id":"…","author":{…},"message":"…",
 "created_at":"…","edited_at":"…","system":"join_channel","reply_count":3,
 "pinned":true,"files":[{"id":"…","name":"report.pdf","size":90210}],
 "attachments":[{"title":"…","text":"…","color":"#ff0000","fields":[…]}],
 "reactions":[{"emoji":"white_check_mark","count":2,"users":["Дмитрий С","Вера П"]}]}
```

- `attachments` carries the content of webhook and alert posts, which leave
  `message` empty. Read both.
- `reactions` is one row per emoji, most reacted first, with everybody who left
  it named. `emoji` is Mattermost's own name without colons — `+1`,
  `white_check_mark`. Absent when nobody reacted, which is most messages: an
  absent field means none were left, not that they were withheld. This is
  often the fastest answer to "was this dealt with" in a channel where people
  ack with ✅ rather than by replying.
- `system` names an automated post (`join_channel`, `add_to_channel`) and is
  absent for anything a person wrote. These are labelled rather than filtered.
- `thread_id` present means this is a reply; fetch the thread for context.
- `files` says an attachment exists and what it is. The `id` on each entry is
  what `file` takes; the contents are never in a message.

### `files`

```json
{"files":[{"id":"…","name":"report.pdf","size":90210,"mime_type":"application/pdf",
  "channel_id":"…","message_id":"…","author":{"username":"vp","name":"Вера П"},
  "created_at":"…"}],
 "channels":{…}}
```

Newest first, with the conversations named alongside exactly as a message
search names them. The query understands `ext:pdf` on top of the `in:`,
`from:`, `before:`/`after:` and quoting a message search takes.

**One page, and it is Mattermost's.** Without Elasticsearch a file search
returns at most 100 hits and answers any `--page` past the first with nothing
at all — an empty second page means the paging is not there, not that the
results ran out. Narrow with `ext:` or `in:` rather than paging.

`message_id` is the message it was attached to: pass it to `thread` to read what
it was sent about, which is usually the thing you actually needed.

### `file`

```bash
mm.py file <id> -o notes.md    # {"path":"notes.md","size":90210}
mm.py file <id> --link         # {"url":"…","expires_at":"…","name":"…","size":…}
```

`-o` defaults to the file id in the current directory, and an existing
destination is refused rather than overwritten — pass `--output` or `--force`.
Files past 25 MB are refused with `413`; open those in Mattermost.

**The link is a capability.** Anyone holding that URL can fetch that one file,
as you, until it expires — so put it in your answer and nowhere else. It stops
working when it expires, when your session ends, and if the gateway's key is
rotated. Minting one is recorded in the audit log against your account.

## What the gateway will not do

Not oversights; each is a decision.

- **No writing.** Nothing posts, edits, marks read, or leaves a reaction. You
  can *read* who reacted to what; adding one yourself is not on offer.
- **No Mattermost public links.** `file --link` mints one of the gateway's own,
  which expires and can be revoked. Mattermost's own public-link endpoint is
  not exposed and will not be: the URL it returns never expires, and the only
  way to withdraw one is to invalidate every public link on the installation.
- **No reading other people's conversations.** Every read by channel or message
  id is gated on the user being a member, checked by the gateway rather than
  delegated to Mattermost — which grants system admins access to everything. A
  refusal is `403 no such conversation, or you are not a member of it`, and it
  says the same thing whether the conversation is somebody else's or does not
  exist. Do not retry it or work around it.
- **No people directory.** `--with` finds conversations with a person, not
  people. There is no way to search the staff list.
- **No arbitrary Mattermost API.** The routes are an allowlist. If something is
  not in the command table, it does not exist here.

## Failures

| Message | Means |
| --- | --- |
| `403` with no JSON body, or `Forbidden` from the gateway | the request never reached the gateway. Access is restricted to known egress addresses, so this means the user is off the office network or VPN. Nothing to retry and nothing the agent can fix — tell them |
| `not authorized yet` | no session; ask the user to approve `login` |
| `the session is over` | the weekly approval lapsed, or the token was replayed; run `login` |
| `403 no such conversation…` | not a member, or no such conversation. Not retryable |
| `400 an identifier in this request is not a mattermost id` | the channel or message id is not one Mattermost would accept from anybody — usually a truncated or invented id rather than one copied from a listing. Not retryable; get the id from `channels` or `search` |
| `502 mattermost is unavailable` | upstream problem; retry once, then report it |
| `400 …` | a malformed parameter — the message names which one |

Concurrent runs are safe: refreshes are serialised with a lock, because two
agents refreshing at once could otherwise trip the gateway's replay detection and
close the session for both.
