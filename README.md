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
Скрипт настройки линкует все три группы, поэтому `skill-importer` нужен только
для точечной установки скилла вне общего чекаута.

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

- симлинки на `AGENTS.md`, `CLAUDE.md`, `.agents/docs` и `.agents/tasks` в
  checkout LevelTravel;
- симлинки на проектные skills из `.agents/skills` в `.claude/skills`;
- записи для всех этих ссылок в `.git/info/exclude`, чтобы локальный overlay не
  попадал в `git status`;
- симлинки на личные skills из `agents_md/.agents/skills` в `~/.codex/skills`;
- симлинки на все shared skills из репозитория `skills` в `~/.codex/skills`;
- зеркало всего каталога `~/.codex/skills` в `~/.claude/skills`, чтобы Codex и
  Claude Code видели одинаковый набор.

Путь к чекауту shared skills берётся из `SKILLS_REPO`, по умолчанию это каталог
`skills` рядом с `agents_md`. Если его нет, скрипт печатает предупреждение и
пропускает этот шаг. Каталоги Codex и Claude переопределяются через `CODEX_HOME`
и `CLAUDE_HOME`.

Скрипт не перезаписывает существующие конфликтующие файлы или ссылки: при
расхождении он завершается с ошибкой и просит разобраться вручную. Повторный
запуск безопасен.
