---
name: integration-task
description: Create LevelTravel integration tasks in Yandex Tracker / Tracker / таск-трекере from the permanent LT-51367 scaffold. By default, draft a structured expanded description for user review and update the created issue only after explicit confirmation; when the user explicitly asks for an integration task without a detailed or expanded description, create only the minimal issue and stop. Use when the user asks Codex to create a LevelTravel integration task, integration ticket, or integration issue in Yandex Tracker.
---

# Integration Task

Use this skill to create LevelTravel integration tasks in Yandex Tracker and prepare high-quality task descriptions.

Before using this skill, read [references/access.md](references/access.md). Always use the existing `yandex-tracker` skill and helper. Resolve the helper once:

```bash
TRACKER_HELPER="${CODEX_HOME:-$HOME/.codex}/skills/yandex-tracker/scripts/tracker.py"
```

Never print, expose, echo, or summarize authentication tokens. Never update the expanded description without explicit user confirmation. Never create a second issue when the user is only editing or approving the description for the issue already created in this conversation.

## Workflow

Work in two main phases by default:

1. Create the Tracker issue immediately with a minimal description using `LT-51367` as the permanent scaffold.
2. Draft an expanded description, show it to the user, and update the same issue only after explicit confirmation.

If the user explicitly says `создай задачу интеграций без детального описания` or otherwise clearly asks to create the task without a detailed or expanded description, use minimal-only mode:

1. Complete Phase 1, including issue verification.
2. Do not start Phase 2, do not generate an expanded-description draft, and do not ask for its approval.
3. Respond with the issue link, issue key, and copied or filled fields, and state briefly that the task was created without a detailed description as requested.

If the user explicitly asks to create a task and provides a title and context or description, do not ask for extra confirmation before creating the minimal issue. If required creation data is missing, ask only for the missing title or minimal task context.

Keep the created issue key in the current conversation state. All later description edits and updates must target exactly that issue.

## Phase 1: Create The Issue From LT-51367

Use `LT-51367` as the permanent field scaffold for new LevelTravel tasks. Treat it as the canonical template, not as an example supplied by the user.

1. Read `LT-51367` with raw output:

   ```bash
   python3 "$TRACKER_HELPER" issue LT-51367 --raw
   ```

2. Copy all relevant fields from `LT-51367`:
   - `queue`
   - `type`
   - `priority`
   - `assignee`
   - `tester`
   - `project.primary`
   - team field `65ba668d034eb51c5204c8d4--team`
   - board fields only when they are explicitly present or assigned automatically through project or queue behavior

3. Use queue `LT` by default for LevelTravel tasks.

4. Use the user's title and raw context for the issue summary and minimal description.

5. Create the issue through the helper:

   ```bash
   python3 "$TRACKER_HELPER" create ...
   ```

6. Pass additional copied fields with `--field-json`.

7. For `project.primary`, prefer `project.primary.key` or the project display name. If Tracker rejects a numeric project `id`, retry with the key or display name. For example, use `Backlog Integrations` instead of `503` when required by the API.

8. If a copied field is not set during creation, immediately update the created issue:

   ```bash
   python3 "$TRACKER_HELPER" update ISSUE-KEY --field-json ...
   ```

9. After creation and any immediate field fixups, verify the created issue:

   ```bash
   python3 "$TRACKER_HELPER" issue ISSUE-KEY --raw
   ```

10. Confirm that the relevant fields from `LT-51367` were transferred. If a non-critical field cannot be transferred, report it clearly instead of silently ignoring it.

11. Respond with:
   - link to the created issue
   - created issue key
   - short list of copied or filled fields
   - in the default workflow, note that the expanded description is still pending user approval
   - in minimal-only mode, note that the task was created without a detailed description as requested

Do not create another issue during later description revisions.

## Phase 2: Draft The Expanded Description

Unless minimal-only mode applies, after creating the minimal issue, transform the user's raw task context into a concise, structured, businesslike Tracker description.

Always include all sections below. If information is missing, write `Пока не указано` or `Требует согласования` instead of asking unnecessary questions.

Use this exact structure:

```markdown
**Проблематика / текущее состояние**
...

**Ожидаемый результат + критерии готовности**
...

Готово, когда:
- ...
- ...

**Заказчик / потребитель**
...

**Контракт и ключевые решения**
- ...

**Проведённые согласования**
Пока не указаны.

**Business value**
...
```

Drafting rules:

- Write in Russian unless the user's task context clearly requires another language.
- Keep the text short, concrete, and businesslike.
- Preserve the original meaning.
- Remove filler and marketing language.
- Keep links, IDs, service names, endpoints, artifact names, and business terms from the source context.
- If the task changes a product or service, state what changes and who benefits.
- Do not ask extra questions when the context is enough for a reasonable task statement.
- Mark unknown customer, contract, decisions, approvals, or criteria as missing or requiring agreement.

After drafting, show the expanded description to the user for review. Clearly say that the Tracker issue has not yet been updated with this expanded description and that an explicit confirmation is required.

## Phase 3: Approval And Description Update

Only update the created issue after explicit user confirmation, such as `подтверждаю`, `обнови задачу`, `можно обновлять`, `ок, залей`, or another clear approval.

If the user sends edits:

1. Apply the edits to the draft description.
2. Show the revised final version.
3. Wait again for explicit confirmation before updating Tracker.

When confirmation is received:

1. Write the approved description to a temporary Markdown file in the current workspace or `/tmp`.
2. Update the same issue created in Phase 1:

   ```bash
   python3 "$TRACKER_HELPER" update ISSUE-KEY --description-file /path/to/description.md --markup-type md
   ```

3. Verify the issue after updating:

   ```bash
   python3 "$TRACKER_HELPER" issue ISSUE-KEY --raw
   ```

4. Respond with:
   - link to the issue
   - issue key
   - brief note that the description was updated

## Example

User context:

```text
Заголовок: Живой поиск в гхц

Краткое описание:
У нас есть Google Hotel Center. Когда гуглишь название отеля - мы появляемся в выдаче Google. Но если в Google поменять даты или количество человек, мы исчезаем из выдачи. Это происходит из-за того, как работает /live_price - live-поиск из Google. Нужно сделать, чтобы ручка возвращала реальный живой поиск, а не пыталась его подменить.
```

Expanded description:

```markdown
**Проблематика / текущее состояние**
В Google Hotel Center при поиске по названию отеля мы показываемся в выдаче. Но если в Google изменить даты или количество человек, мы пропадаем из выдачи. Причина в текущем поведении `/live_price`: ручка не отдает реальный живой поиск, а пытается его подменять. Из-за этого Google не получает корректный live response и перестает показывать нас в релевантной выдаче.

**Ожидаемый результат + критерии готовности**
Нужно сделать так, чтобы `/live_price` возвращал настоящий live-поиск, а не подмененный ответ.

Готово, когда:
- `/live_price` отдает реальный live search;
- Google продолжает видеть нас при изменении дат и количества человек;
- поведение соответствует требованиям live-поиска из Google;
- нет подмены, которая искажает результаты;
- проверен целевой сценарий поиска в Google Hotel Center.

**Заказчик / потребитель**
Команда Google Hotel Center, пользователи, которые ищут отели через Google, и команда, отвечающая за live-поиск.

**Контракт и ключевые решения**
- Изменения касаются ручки `/live_price`.
- Нужно убрать подмену и вернуть реальный live search.
- Формат ответа должен соответствовать требованиям Google для live-поиска.

**Проведённые согласования**
Пока не указаны.

**Business value**
Возвращает нас в релевантную выдачу Google Hotel Center, увеличивает видимость отелей при изменении параметров поиска и напрямую влияет на трафик и бронирования.
```
