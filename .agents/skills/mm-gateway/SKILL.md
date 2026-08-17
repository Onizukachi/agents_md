---
name: mm-gateway
description: 'Read the user''s own Mattermost messages and attachments through mm-gateway. Use when asked about Mattermost or chat — "what did I miss", "catch me up on #channel", "what did we decide about X", "my conversations with <person>", "find that message about Y", "what is in the file <person> sent me", "give me a link to that attachment", unread mentions, or threads awaiting a reply. Also use before answering from memory about anything discussed in chat. Requires the shell to reach the gateway from a Level Travel office or the corporate VPN; from anywhere else every call is refused at the edge. See references/access.md.'
---

# Reading Mattermost

`scripts/mm.py` reads the user's own Mattermost. It never handles a Mattermost
token: the gateway holds that and exposes a fixed set of read operations. You can
only see what the user can see.

Everything returns compact JSON on stdout. Errors go to stderr with a non-zero
exit.

```bash
SKILL=<this directory>
python3 "$SKILL/scripts/mm.py" channels --active-since 7d --limit 30
```

## You have to be on the network first

The gateway answers only from Level Travel office addresses and the corporate
VPN. Everywhere else is refused at the edge, before any of this matters.

That refusal is a **403 on every call, including `login`**, and it is the one
failure that looks like a permissions problem and is not. If the very first
command fails that way, do not run `login` and do not tell the user their
Mattermost access is wrong: ask them to connect the corporate VPN. A session
that worked yesterday and 403s today usually means the VPN dropped, not that
anything was revoked.

## Authorization

One approval per week, by the human, in a browser. A session lasts seven days
and no longer — an unattended or scheduled run will stop working until its
owner approves again, and cannot approve on their own behalf.

**Exit code 2 means the human has to approve again**, and nothing else does.
Check the code rather than the wording of the error:

| Exit | Meaning | Do |
| --- | --- | --- |
| 0 | fine | read stdout |
| 2 | no session, or it expired | run `login`, below |
| 1 | anything else — a bad request, a channel you are not in, the gateway down | report it; `login` fixes none of them |

```bash
python3 "$SKILL/scripts/mm.py" login
```

It prints a URL and a code to stderr and then waits. **Show the user both and
ask them to approve** — they have to click it; you cannot. It returns once they
have. Don't run `login` speculatively; run it when a read exits 2.

A gateway that is redeploying answers 1, not 2. Reads already retry a few times
over about three seconds, so an exit 1 that says the gateway is unreachable has
survived the retries and is worth reporting rather than papering over with a
device flow the user does not need.

The refresh token lives in `~/.config/mm-gateway/tokens.json` (0600). Never print
it, copy it, or pass it anywhere.

## Ask for less than everything

This is the part that matters. A measured account had **630 conversations and
37 touched in the last week** — the ratio, not the numbers, is the point. Its
unfiltered listing ran to ~42,000 tokens, a fifth of a 200k context, and
answered almost nothing.

| Question | Do this | Not this |
| --- | --- | --- |
| "what did I miss" | `channels --unread` | list everything and diff |
| "catch me up on X" | `pinned <id>` first, then `messages` | page back through history |
| "what did we decide about X" | `search 'X'` | read channels looking for it |
| "my chats with Vera" | `channels --with vera@…` | list all and grep |
| "the #X channel" | `channels --name X` | list all and match on the name |
| "last N alerts/tickets in #X" | `search "in:<slug> <marker>"` | page `messages` and filter |
| "what's active" | `channels --active-since 7d --limit 30` | `channels` |

`search` first, almost always. Listing conversations to find a discussion is
the expensive way to do a cheap thing.

A single page of 60 messages from a busy channel runs to ~20,000 tokens. Use
`--limit`, and prefer `pinned` when catching up: one channel here has 2,043
unread messages and 5 pinned ones, and the pinned ones are what a human chose
to keep.

**`messages --limit N` already gives you the newest N.** "Oldest first" is the
order within the page, not which page arrives — with no cursor you get the live
end of the channel. Asking for 20 to keep the last 2 is a mistake that costs
six times the tokens and looks like it worked.

## Two things that will silently mislead you

**`in:` needs the `slug`, not the `name`.** Mattermost matches `in:` against a
channel's identifier, exactly, never its display name — and a wrong one returns
*zero hits with no error*. Every conversation reports both. Ten of this
installation's 42 named channels differ: `Добро пожаловать!` is `town-square`,
`обеды` is `cb0u45dqb`.

```bash
mm.py search "in:town-square deploy"      # slug — works
mm.py search "in:Добро пожаловать! deploy" # name — silently nothing
```

Never guess the slug from what the user called the channel. `channels --name X`
reports both, and is one call: look it up, then build the `in:` from the `slug`
it returns. A name that happens to be its own slug is luck, not a rule.

**Empty `message` fields are not empty messages.** Every alert and webhook post
puts its content in `attachments` instead. If you read only `message`, the
channels most worth watching look like rows of blank lines.

**Two different things are called an attachment, and only one is a file.**
`attachments` is the webhook content above. `files` is what somebody uploaded,
and it carries an id and a name — never the contents. Which command you want
depends on who the file is for:

- **You have to read it** — `file <id> -o notes.md`, then open what it wrote.
  That is the answer to "what's in that spreadsheet Dave sent me".
- **A person has to have it** — `file <id> --link` returns a URL to put in your
  answer. It opens in any browser with no Mattermost login and lasts fifteen
  minutes, so mint it when you hand it over rather than in advance. **Say that
  it needs the VPN.** The link points at the gateway, which is reachable only
  from an office network or the corporate VPN — off them it is refused at the
  edge, which looks like a broken link rather than a network problem.

Never build a Mattermost URL by hand. `https://mm.lvtv.me/api/v4/files/<id>`
works only in a browser already signed in to Mattermost — which the person
reading your answer is usually not, because they read Mattermost in its app.

## Commands

| | |
| --- | --- |
| `channels [--active-since 7d] [--limit N] [--kind …] [--unread] [--with PERSON] [--name CHANNEL]` | conversations, most recent first |
| `search QUERY [--limit N] [--page N]` | messages across everything you can see |
| `threads [--unread] [--since TS] [--limit N]` | threads you follow |
| `saved [--limit N] [--page N]` | messages you bookmarked |
| `messages CHANNEL_ID [--limit N] [--before ID] [--after ID] [--since TS]` | the newest N of one conversation, ordered oldest-first |
| `thread MESSAGE_ID [--limit N]` | a message and its replies. Accepts the id from a `…/pl/<id>` permalink |
| `pinned CHANNEL_ID` | what somebody chose to keep |
| `files QUERY [--limit N] [--page N]` | attachments across everything you can see. Adds `ext:` to the search syntax |
| `file FILE_ID [-o PATH] [--force]` | writes the attachment to disk and reports where |
| `file FILE_ID --link` | a URL to hand a person, good for fifteen minutes |
| `whoami` | the Mattermost account this maps to |

`--with` takes an email, a username with or without `@`, or part of a display
name. `--name` takes a channel's slug or display name, with or without a
leading `#` — an exact match wins, and substring matches come back only when
nothing matched outright. The two cannot be combined: `--with` searches direct
and group messages, `--name` searches channels somebody named. `--kind` takes
`public`, `private`, `direct`, `group`, comma-separated. `--active-since` takes
`7d`, `48h`, `30m` or an RFC 3339 timestamp.

**`--name` is how you turn a channel into an id.** Every other command takes a
`CHANNEL_ID`, and it is the one thing a user never gives you. Do not reach for
`--active-since` to make a full listing affordable while hunting for one
channel: a channel quiet for longer than the window comes back empty, which
looks exactly like no such channel.

Messages carry `reactions` when anybody left one: `{emoji, count, users}`, one
row per emoji with the people named. In a channel where a request is closed by
somebody putting a ✅ on it rather than by replying, that field is the answer to
"was this dealt with". You can read them; you cannot leave one. The one place
they never appear is the `root` of a `threads` listing — Mattermost does not
send them there, so read `thread <id>` rather than concluding nobody reacted.

See [references/api.md](./references/api.md) for the search syntax, the response
shapes, cursors and paging, and what the gateway will not do.
[references/access.md](./references/access.md) covers the network requirement
and the one-approval-per-week session.

## When you report back

Name people and channels, not IDs — the responses already resolve both. Quote
what was actually said rather than paraphrasing a decision into existence, and
link nothing you did not read. If a search returned nothing, say so; it is a
real answer, and the two silent-failure modes above are the first thing to
check before concluding a discussion never happened.
