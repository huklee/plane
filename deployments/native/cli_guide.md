# Plane CLI guide

Self-hosted Plane, e.g. served at `https://<host>/plane` (see README.md).
CLI control uses Plane's stock REST API v1; nothing in Plane was modified for it.

## Setup

| What     | Where                                                                                                                |
| -------- | -------------------------------------------------------------------------------------------------------------------- |
| CLI      | `deployments/native/planecli` (Python stdlib, no deps)                                                               |
| API key  | `$PLANE_RUNTIME/api-token` (mode 600), or `export PLANE_API_KEY=...`                                                 |
| Required | `PLANE_URL` (https://<host>/plane) · `PLANE_WORKSPACE` (slug) · optional `PLANE_PROJECT` (identifier, default `SBX`) |

New key: Plane → Profile settings → Personal Access Tokens. Optional: symlink `planecli` into your PATH.

## planecli

```sh
planecli projects                     # identifiers + ids
planecli states                       # Backlog · Todo · In Progress · Done · Cancelled
planecli list [--state "In Progress"] # SBX-n  state  priority  start → due  title
planecli get SBX-3                    # + created/updated/completed timestamps, web link

planecli add "Fix login" --state todo --priority high --start 2026-10-02 --due 2026-10-09 --desc "..." --assign-me
planecli edit SBX-3 --state "In Progress" --due 2026-10-12
planecli edit 3 --name "New title" --priority urgent     # bare number = PLANE_PROJECT
planecli edit 3 --clear-dates
planecli comment SBX-3 "progress: 60%"
planecli edit 3 --state done          # sets completed_at automatically
planecli history SBX-3                # every field change with timestamps
planecli delete SBX-3
PLANE_PROJECT=OPS planecli list       # another project
```

- `--state` matches a state **name** or **group** (`backlog`, `unstarted`, `started`, `completed`, `cancelled`), case-insensitive
- `--priority`: `urgent` `high` `medium` `low` `none`

## What can and can't change (stock Plane)

| Field                        | Settable  | Notes                                                             |
| ---------------------------- | --------- | ----------------------------------------------------------------- |
| status (state)               | yes       | progress = state group: backlog → unstarted → started → completed |
| priority, title, description | yes       |                                                                   |
| start / due date             | yes       | **date only** (`YYYY-MM-DD`); a time is rejected                  |
| assignees, labels            | yes (API) | CLI: `--assign-me`; labels via curl (below)                       |
| comments                     | yes       | use for free-form progress notes ("progress: 60%")                |
| created_at / updated_at      | no        | server time; a `created_at` in the request is ignored             |
| completed_at                 | no        | set to "now" when moved to a completed state                      |
| progress %                   | —         | no such field in Plane CE                                         |

## Raw API (curl)

```sh
B=$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE
H=(-H "X-API-Key: $PLANE_API_KEY" -H "Content-Type: application/json")
P=$(curl -s "${H[@]}" $B/projects/ | python3 -c "import sys,json;print([p['id'] for p in json.load(sys.stdin)['results'] if p['identifier']=='SBX'][0])")

curl -s "${H[@]}" $B/work-items/SBX-3/                                   # read by identifier
curl -s "${H[@]}" $B/projects/$P/states/                                 # state ids
curl -s "${H[@]}" $B/projects/$P/labels/                                 # label ids
curl -s "${H[@]}" -X POST  $B/projects/$P/work-items/ -d '{"name":"x","priority":"low","target_date":"2026-10-20"}'
curl -s "${H[@]}" -X PATCH $B/projects/$P/work-items/<id>/ -d '{"state":"<state-id>","labels":["<label-id>"]}'
curl -s "${H[@]}" $B/projects/$P/work-items/<id>/activities/             # history
```

Other v1 resources under `projects/$P/`: `cycles/`, `modules/`, `labels/`, `members/`, `work-items/<id>/{comments,links,relations,attachments}/`. Rate limit: 120 requests/minute per key (`API_KEY_RATE_LIMIT` in `api.env`).

## Server operations

```sh
deployments/native/plane.sh status | start | stop | restart
```

- Logs: `$PLANE_RUNTIME/logs/` · config: `$PLANE_RUNTIME/{api,live,build,native}.env`
- The front proxy must forward `/plane` and `/plane-uploads` (README.md)
- Not started at boot — run `plane.sh start` after a reboot
- Rebuild the web apps after changing `build.env` or pulling Plane: `deployments/native/build.sh` (then `plane.sh restart`)
