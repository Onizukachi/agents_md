# Access Requirements

## Summary

- Required access: a Level Travel Mattermost account provisioned through SSO, and network access to `https://mm-gateway.admin.lvtv.me` from a Level Travel office or the corporate VPN. The gateway allowlists source addresses at its edge; everything else is refused before a request reaches it.
- Local credentials/config: none to obtain by hand. The helper runs a Keycloak device flow and stores the resulting refresh token at `~/.config/mm-gateway/tokens.json` (0600). Override the location with `MM_GATEWAY_HOME`, and the gateway URL with `MM_GATEWAY_URL`. `MM_CLIENT_ID` overrides the name the helper puts on each request for the gateway's log — it defaults to the script version, the account of the last approval (or the local user, if there has never been one) and the hostname, and is worth setting to something meaningful for an unattended or shared-machine run.
- Local tools: `python3`, and a browser for the human to approve in.
- Request from: the infrastructure team, in `#infra-issues`. VPN access is the usual ask; a Mattermost account that predates SSO cannot be resolved and needs one of them to say so.

## Setup

1. Connect the corporate VPN, or work from an office network.
2. From the skill directory, run `python3 scripts/mm.py login`.
3. Open the URL it prints, check the code on the page matches the one it printed, and approve. The agent cannot do this step.
4. Approval lasts seven days. After that any command exits 2 and the human approves again.

## Validation

From the skill directory:

```bash
python3 scripts/mm.py whoami
```

It should print the Mattermost account the caller resolves to. What the failures mean:

| Symptom | Cause |
| --- | --- |
| `403` on every command, including `login` | not on the VPN or an office network |
| a file link "does not work" for somebody | same cause: links point at the gateway, so they open from an office network or the VPN and nowhere else |
| exit code 2 | no session yet, or it expired — run `login` |
| `no mattermost account for this identity` | the account is not SSO-provisioned, or its email is unverified in Keycloak |

Never print, copy, or pass on the contents of `tokens.json`. It is a live
credential, and the gateway treats a token presented twice as theft: it closes
the session for every agent the user has.

## What this does not grant

Reads only, and only what the user can already see. The gateway holds the
Mattermost credential and never discloses it, checks channel membership itself
rather than trusting Mattermost's permission model, and exposes no endpoint
that writes, posts, or deletes anything.
