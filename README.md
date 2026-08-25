# agents_md

Репозиторий содержит личные материалы для работы Codex и Claude Code с проектом
LevelTravel. Он используется как источник для симлинков в локальном checkout
LevelTravel и в глобальных каталогах агентов (`~/.codex/skills`,
`~/.claude/skills`); копии этих материалов в основном репозитории не хранятся.

## Содержимое

- `AGENTS.md` — основные инструкции для агентов в LevelTravel.
- `CLAUDE.md` — симлинк на `AGENTS.md`.
- `CONTEXT.md` — доменный словарь проекта.
- `.agents/docs/` — дополнительная проектная документация для агентов.
- `.agents/skills/` — личные skills; каждая подпапка линкуется целиком, без
  отдельного списка.
- `.agents/tasks/` — task artifacts (`SPEC.md`, `ticket-<NN>-<slug>.md`).
  Каталог появляется, когда `to-spec`/`to-tickets` создают первый артефакт: git
  не хранит пустые каталоги, поэтому на свежем клоне симлинк `.agents/tasks` в
  checkout LevelTravel до этого момента висит битым — это ожидаемо.
- `scripts/setup_leveltravel_agent_links.sh` — настройка симлинков на новой
  машине.

Skills, относящиеся к основному workflow LevelTravel (`leveltravel-pr-workflow`,
`leveltravel-tests` и прочие), лежат в самом репозитории LevelTravel и линкуются
скриптом настройки. Skills из общего реестра (`integration-*`, `lt-metrics`,
`lvtv-elastic-logs`, `mm-gateway`, `yandex-*` и т. д.) ставит и обновляет
`lt-skills sync` — он пишет собственные managed-копии в `~/.codex/skills` и
`~/.claude/skills`, и скрипт настройки их не трогает.

## Настройка симлинков

Если `agents_md` расположен рядом с checkout LevelTravel, из корня LevelTravel
выполни:

```bash
../agents_md/scripts/setup_leveltravel_agent_links.sh "$PWD"
```

Аргументом передаётся путь к локальному checkout LevelTravel. Если запускать
скрипт из корня `agents_md`, путь можно передать явно:

```bash
scripts/setup_leveltravel_agent_links.sh /путь/к/leveltravel
```

Без аргумента скрипт предполагает, что каталог `leveltravel` расположен рядом
с `agents_md`.

Скрипт создаёт или проверяет:

- симлинки на `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, `.agents/docs` и
  `.agents/tasks` в checkout LevelTravel;
- симлинки на проектные skills из `<leveltravel>/.agents/skills` в
  `<leveltravel>/.claude/skills`, чтобы Claude Code находил их так же, как Codex
  находит `.agents/skills` напрямую;
- записи для всех этих ссылок в `.git/info/exclude` (`/AGENTS.md`,
  `/CLAUDE.md`, `/CONTEXT.md`, `/.agents/docs`, `/.agents/tasks`,
  `/.claude/skills`), чтобы локальный overlay не попадал в `git status`;
- симлинки на личные skills из `agents_md/.agents/skills` в `~/.codex/skills`
  и `~/.claude/skills`.

Каталоги Codex и Claude переопределяются через `CODEX_HOME` и `CLAUDE_HOME`.

Скрипт не перезаписывает существующие конфликтующие файлы или ссылки: при
расхождении он завершается с ошибкой и просит разобраться вручную. Повторный
запуск безопасен.
