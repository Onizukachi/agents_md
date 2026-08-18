# agents_md

Репозиторий содержит личные материалы для работы Codex с проектом LevelTravel.
Он используется как источник для симлинков в локальном checkout LevelTravel и
в глобальном каталоге Codex; копии этих материалов в основном репозитории не
хранятся.

## Содержимое

- `AGENTS.md` — основные инструкции для Codex в LevelTravel.
- `CLAUDE.md` — симлинк на `AGENTS.md`.
- `.agents/docs/` — дополнительная проектная документация для агентов.
- `.agents/tasks/` — явно созданные task artifacts.
- `.agents/skills/` — личные skills; каждая подпапка линкуется целиком, без
  отдельного списка.
- `scripts/setup_leveltravel_agent_links.sh` — настройка симлинков на новой
  машине.

Shared skills хранятся в отдельном репозитории `skills`, а skills, относящиеся
к основному workflow LevelTravel, находятся в самом репозитории LevelTravel.

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

Скрипт создаёт или проверяет симлинки на `AGENTS.md`, `CLAUDE.md`,
`.agents/docs`, `.agents/tasks` и личные skills в `~/.codex/skills`. Он не
перезаписывает существующие конфликтующие файлы или ссылки.
