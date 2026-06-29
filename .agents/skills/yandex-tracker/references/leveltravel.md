# LevelTravel Tracker Context

Use this reference for LevelTravel-specific Yandex Tracker work.

## Stable Boards And Queues

- Scrum board: `2`
- Epic Flow board: `214`
- Dev Epics board: `658`
- Development task queue: `LT`
- EpicFlow queue: `EPICFLOW`

Discover the current Scrum sprint with:

```bash
python3 "$TRACKER_HELPER" current-sprint
```

## Stable Fields

- Scrum task team field: `65ba668d034eb51c5204c8d4--team`
- EpicFlow development team field: `69c2cd23dcc4e4691efad1ad--dev_team`
- Story points field: `storyPoints`

Known team values include:

- `WebFront`
- `WebBack`
- `Integrations`
- `iOS`
- `Android`
- `Dynamics`
- `FinDoc`
- `Internal Affairs`

## Local Defaults

The helper has LevelTravel defaults compiled in. They can be overridden in `~/.yandex-tracker.env`:

```dotenv
YANDEX_TRACKER_DEFAULT_BOARDS=2:Scrum,214:EpicFlow,658:DevEpics
YANDEX_TRACKER_SCRUM_BOARD_ID=2
YANDEX_TRACKER_EPICFLOW_BOARD_ID=214
YANDEX_TRACKER_DEV_EPICS_BOARD_ID=658
YANDEX_TRACKER_DEV_QUEUE=LT
YANDEX_TRACKER_EPIC_QUEUE=EPICFLOW
YANDEX_TRACKER_TASK_TEAM_FIELD=65ba668d034eb51c5204c8d4--team
YANDEX_TRACKER_EPIC_TEAM_FIELD=69c2cd23dcc4e4691efad1ad--dev_team
YANDEX_TRACKER_STORY_POINTS_FIELD=storyPoints
```

## Read-Only Analysis Commands

Current sprint:

```bash
python3 "$TRACKER_HELPER" current-sprint
```

EpicFlow coverage for all Scrum tasks in the current sprint:

```bash
python3 "$TRACKER_HELPER" epicflow-coverage --sprint current
```

EpicFlow coverage for one team:

```bash
python3 "$TRACKER_HELPER" epicflow-coverage --sprint current --team WebFront
```

Full project/task details:

```bash
python3 "$TRACKER_HELPER" epicflow-coverage --sprint current --team WebFront --details
```

Cluster tasks that have no development project:

```bash
python3 "$TRACKER_HELPER" no-project-clusters --sprint current
```

Compare current Scrum sprint against active EpicFlow issues on the Epic Flow board:

```bash
python3 "$TRACKER_HELPER" scrum-epicflow-alignment --sprint current
python3 "$TRACKER_HELPER" scrum-epicflow-alignment --sprint current --details
```

Summarize recent team activity and productivity:

```bash
python3 "$TRACKER_HELPER" activity-summary --days 14
python3 "$TRACKER_HELPER" activity-summary --since 2026-06-08 --until 2026-06-22 --with-changelog
```

Use `activity-summary --with-changelog` when the user asks about productivity or throughput: it reads status changelog and counts actual transitions into `Завершено`, `Готово к релизу`, or `ReadyToProduction`. Without `--with-changelog`, done counts are based on the current status of recently updated tasks.
