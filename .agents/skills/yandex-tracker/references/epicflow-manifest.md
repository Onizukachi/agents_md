# EpicFlow Manifest Rules

Use this reference when analyzing LevelTravel initiatives, Scrum sprint tasks, project linkage, or EpicFlow coverage.

## Core Principle

An EpicFlow issue is the single source of truth for initiative status.

Do not treat development task statuses, project statuses, Gantt state, or portfolios as the initiative status source.

## Required Model

- Every initiative must be represented by exactly one `EPICFLOW` issue.
- Every initiative must have a linked development project.
- Development decomposition happens inside the project: epics, tasks, and subtasks.
- Product development tasks must link to EpicFlow through their development project.
- EpicFlow status must be updated whenever the initiative changes stage.
- Initiative closure happens by completing the EpicFlow issue.

## Analysis Rules

When checking Scrum tasks:

1. Discover the current Scrum sprint.
2. Load `LT` tasks in that sprint.
3. Group by the Scrum task team field when the user asks for a team-specific report.
4. Load `EPICFLOW` issues with their `project` and `dev_team` fields.
5. Join development tasks to EpicFlow through `project.primary` and `project.secondary`.
6. Report these findings:
   - tasks without any project;
   - projects without EpicFlow;
   - projects with exactly one EpicFlow;
   - projects with multiple EpicFlow;
   - tasks whose project has EpicFlow but not for the requested team;
   - team/status/assignee counts.

## Interpretation

- Task without project: do not create EpicFlow directly from the task. First find or create the development project.
- Project without EpicFlow: candidate for creating exactly one EpicFlow issue if it represents a real initiative.
- Project with multiple EpicFlow: cleanup candidate; decide which EpicFlow owns the initiative or split the project.
- Bucket projects like `Backlog`, `Bugs`, `Other tasks`, or broad tech-debt projects usually need human triage. Do not blindly create one EpicFlow for the whole bucket.
- Multiple tasks without project that share a product or technical stream are candidates for a new development project, then a single EpicFlow issue.

## Useful Commands

```bash
python3 "$TRACKER_HELPER" epicflow-coverage --sprint current
python3 "$TRACKER_HELPER" epicflow-coverage --sprint current --team WebBack
python3 "$TRACKER_HELPER" epicflow-coverage --sprint current --details
python3 "$TRACKER_HELPER" no-project-clusters --sprint current
```
