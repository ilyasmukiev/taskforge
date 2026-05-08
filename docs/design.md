# taskforge — дизайн

Дата: 2026-05-08
Автор: Claude (по идее ilyasmukiev)

## 0. Цель

Длительная фоновая работа Claude Code: пока пользователь не за компьютером, **N параллельных команд** генерируют **качественный корпус решённых задач** в выбранных темах. Качество > количества: каждая задача проверяется отдельным Reviewer-агентом, при недостаточном качестве отправляется на переделку, при принципиальных дефектах — отбрасывается.

Корпус накапливается между запусками, не сбрасывается, лежит в глобальной папке вне репозиториев.

## 1. Архитектура верхнего уровня

```
                  ┌──────────────────────────────────┐
                  │   taskforge orchestrator         │
                  │   (Python, foreground/daemon)    │
                  │   wizard / лимиты / таймер /     │
                  │   раздача тем / graceful stop    │
                  └──────────────┬───────────────────┘
                                 │  файлы-сигналы
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
        ┌──────────┐       ┌──────────┐       ┌──────────┐
        │  TEAM 1  │       │  TEAM 2  │       │  TEAM 3  │
        │  3 шага: │       │  3 шага: │       │  3 шага: │
        │ planner →│       │ planner →│       │ planner →│
        │ executor→│       │ executor→│       │ executor→│
        │ reviewer │       │ reviewer │       │ reviewer │
        │ (claude  │       │ (claude  │       │ (claude  │
        │  -p ...) │       │  -p ...) │       │  -p ...) │
        └────┬─────┘       └────┬─────┘       └────┬─────┘
             │                  │                  │
             └──────────────────┼──────────────────┘
                                ▼
              ~/.claude/skills-data/taskforge/
                corpus/<topic>/<YYYY-MM-DD-task-NNN>/
                  task.md     solution.md     review.md
                  code/       meta.json       (checkpoint.json)
                index.json    state/          logs/
```

Команда — это **последовательность из 3+ subprocess-вызовов** `claude -p` (по одному на роль), не tmux-pane. Параллельность достигается на уровне «N команд одновременно идут по своему пайплайну». Внутри команды — последовательность.

**Файлы-сигналы** между оркестратором и командами:
- `state/runtime.json` — оркестратор пишет: текущие `usage_percent`, `time_left_seconds`, `should_stop`. Команда смотрит перед каждым шагом.
- `state/teams/<team-id>/status.json` — команда пишет: `phase`, `topic`, `task_id`, `started_at`, `last_heartbeat`. Оркестратор читает.

## 2. Команда: внутреннее устройство

Каждая команда — экземпляр класса `TeamRunner` в Python. Жизненный цикл одной задачи:

1. **Получить тему** от оркестратора (через `topic_queue` файла или round-robin).
2. **Прочитать контекст**: последние 50 заголовков задач этой темы из `index.json` (для дедупликации) + список открытых чекпоинтов этой темы.
3. **Проверить чекпоинт**: если есть незавершённый — продолжаем с него, иначе — новая задача.
4. **Planner** (`claude -p --model <planner_model>` с системным промптом из `prompts/planner.md`): генерирует условие задачи. Вход: тема + список последних заголовков. Выход: `task.md` (markdown с условием) + краткий заголовок.
5. **Дедуп-чек**: считаем sha256 от нормализованного условия. Если совпадение в `index.json` — возврат к шагу 4 (до 3-х попыток, потом тема пропускается).
6. **Executor** (`claude -p --model <executor_model>`): получает `task.md`, пишет `solution.md` (+ опционально файлы в `code/`).
7. **Reviewer** (`claude -p --model <reviewer_model>`): получает `task.md` + `solution.md`, выдаёт `review.md` со структурированным вердиктом: `pass` / `revise` / `discard`.
8. **Цикл переделки**: если `revise` — Executor переписывает с фидбеком (max 2 раза), затем — снова Reviewer.
9. **Финализация**: при `pass`/`discard`/исчерпании итераций — пишем `meta.json`, удаляем `checkpoint.json` (если был), добавляем запись в `index.json`.
10. **Хартбит** между шагами: команда пишет в `status.json`, проверяет `runtime.json` на стоп-сигнал. Если стоп — сохраняет `checkpoint.json` (текущая фаза, итерация, накопленное содержимое) и завершается.

## 3. Лимиты, таймер, чекпоинты

### Источник usage

OMC HUD кеширует ответы Anthropic OAuth API в `~/.claude/plugins/oh-my-claudecode/.usage-cache.json` (TTL 30s). Оркестратор:

1. Сначала читает кеш OMC (если файл существует и `timestamp` свежий — берём оттуда).
2. Иначе — собственный вызов `https://api.anthropic.com/api/oauth/usage` с Bearer-токеном из macOS Keychain (`security find-generic-password -s "Claude Code-credentials" -w`) или `~/.claude/.credentials.json`.
3. Кеширует результат на 30 сек, чтобы не нагружать API.

Поля: `fiveHourPercent`, `weeklyPercent`, `monthlyPercent`, `fiveHourResetsAt`, `weeklyResetsAt`.

### Стоп-условия

Любое из, в OR-логике:
- **Таймер**: `time.now() - started_at >= duration_seconds`.
- **Сессионный лимит**: `fiveHourPercent >= session_limit_percent` (абсолют).
- **Недельный лимит**: `weeklyPercent >= weekly_limit_percent` (абсолют).

Проверка: каждые 5 секунд в loop оркестратора. При срабатывании — `should_stop = true` в `runtime.json`.

### Graceful shutdown

1. `should_stop = true` → новые задачи не выдаются.
2. Команды дочитывают `runtime.json` между шагами своего пайплайна; если `should_stop` — останавливаются после текущего `claude -p` вызова.
3. Если команда в середине задачи — пишет `checkpoint.json`:
   ```json
   {"task_id":"...", "topic":"...", "phase":"executor",
    "iteration":1, "task_md":"...", "solution_md_so_far":"...",
    "review_md_so_far": null}
   ```
4. Команды завершаются → оркестратор пишет финальный отчёт в `logs/` и выходит.

### Resume

При запуске (`taskforge start` или `taskforge resume`):
1. Сканируем `~/.claude/skills-data/taskforge/corpus/*/*/checkpoint.json`.
2. Перед стартом новых задач первые N команд получают эти чекпоинты.
3. Команда восстанавливает фазу и продолжает (например, фаза `executor` iter 1 — снова вызывает Executor с тем же `task.md` и теми же inputs).
4. Завершив — удаляет `checkpoint.json`.

## 4. Корпус и индексация

### Расположение

`~/.claude/skills-data/taskforge/`:
```
corpus/
  code-block/                  # темы как slug
    2026-05-08-task-0001/
      task.md                  # условие
      solution.md              # решение
      review.md                # вердикт + комментарии
      code/                    # файлы кода (если кодовая тема)
      meta.json                # метаданные
      checkpoint.json          # ТОЛЬКО если задача незавершена
  math-analysis/
  ...
index.json                     # массив всех записей
state/
  runtime.json                 # оркестратор → команды
  teams/<team-id>/status.json  # команды → оркестратор
config.json                    # последний wizard
logs/run-<timestamp>.log
```

### `meta.json`

```json
{
  "id": "code-block-2026-05-08-task-0001",
  "topic": "code-block",
  "title": "Реализовать LRU кэш на Python",
  "condition_hash": "sha256:...",
  "models": {"planner": "opus", "executor": "sonnet", "reviewer": "opus"},
  "verdict": "pass",
  "iterations": 1,
  "started_at": "2026-05-08T20:55:01Z",
  "finished_at": "2026-05-08T20:58:43Z",
  "wall_clock_seconds": 222,
  "team_id": "team-2",
  "topic_seq": 17
}
```

### `index.json`

Массив объектов формата:
```json
{"id":"...", "topic":"...", "title":"...", "condition_hash":"...", "verdict":"...", "path":"corpus/.../...", "finished_at":"..."}
```

Атомарная запись: пишем во временный файл, `os.rename` поверх. Только оркестратор пишет (команды через него — `state/teams/<id>/index_append.json` сигнал).

### Дедупликация

Простая, без эмбеддингов:
- При генерации условия Planner-у в контекст передаются последние 50 заголовков темы.
- После генерации — sha256 от нормализованного условия (lower, trim, multi-space → single).
- Если хеш в `index.json` — повтор Planner-а с явной пометкой «такое уже было».
- 3 попытки, потом тема пропускается на этом раунде (round-robin переходит дальше).

## 5. Wizard и UX запуска

Skill активируется через Claude Code (`/taskforge` или фразой). SKILL.md инструктирует Claude:

1. Использовать `AskUserQuestion` (или fallback Bash interactive script) для 8 вопросов:
   1. Модель Planner-а (default `opus`)
   2. Модель Executor-а (default `sonnet`)
   3. Модель Reviewer-а (default `opus`)
   4. Число параллельных команд (default `3`, hint «оптимально 3»)
   5. Длительность (`5h`, `30m`, формат `<число><h|m>`)
   6. Сессионный лимит, % абсолют (default `50`)
   7. Недельный лимит, % абсолют (default `50`)
   8. Темы (multi-select из 10, default — все)
2. Сохранить ответы в `~/.claude/skills-data/taskforge/config.json`.
3. Запустить `python3 ~/.claude/skills/taskforge/bin/taskforge start --config <path> &` в фоне через `nohup`.
4. Сообщить пользователю PID и путь к логу.

Команды CLI:
- `taskforge start [--config FILE]` — запуск из готового config'а
- `taskforge wizard` — interactive wizard через stdin (для тех, кто запускает руками)
- `taskforge status` — состояние работающего оркестратора
- `taskforge stop` — graceful stop
- `taskforge resume` — продолжить с чекпоинтов

## 6. Темы

10 фиксированных тем (slug — заголовок):

| slug | заголовок |
|------|-----------|
| `code-block` | Писать код с нуля — один блок |
| `code-project` | Писать с нуля небольшой проект по плану |
| `bug-block` | Баг / оптимизация / синтаксис в одном блоке кода |
| `bug-project` | Баг / оптимизация / синтаксис в проекте |
| `web-search` | Веб-поиск релевантного / актуального ответа |
| `tools` | Работа с инструментами |
| `planning` | Планирование |
| `math-analysis` | Математический анализ |
| `higher-math` | Высшая математика |
| `logic` | Логика |

Round-robin по выбранным темам. Каждая команда получает свою тему, через каждые `N=число команд` циклов темы повторяются (но задачи разные за счёт дедупа).

## 7. Структура репозитория и публикация

```
taskforge/
  SKILL.md                # Skill manifest, читается Claude Code
  README.md               # Двуязычный (RU + EN)
  LICENSE                 # MIT
  .gitignore              # игнор для тестовой среды
  bin/
    taskforge             # CLI entrypoint (Python shebang)
  prompts/
    planner.md            # системный промпт Planner
    executor.md           # системный промпт Executor
    reviewer.md           # системный промпт Reviewer
  topics.yaml             # справочник тем (slug → title + hints)
  docs/
    design.md             # этот файл
  install.sh              # установка одной командой
```

Репо — публичный `github.com/ilyasmukiev/taskforge`. README ставится в порядке: установка → запуск → как Skill устроен → конфигурация → корпус → стоп → лимиты → разработка.

Корпус и состояние **никогда** не попадают в репо — `.gitignore` исключает `~/.claude/skills-data/taskforge/`. Корпус — приватные данные пользователя.

## 8. Тестирование (smoke)

При установке:
- `taskforge --version` отвечает.
- `taskforge wizard` корректно собирает ответы (проверка через echo-pipe).
- `taskforge start --config sample.json --dry-run` имитирует один цикл без вызова `claude` — проверяет логику оркестратора.
- Реальный `taskforge start` на 1 минуту, 1 команда, 1 тема — проверяет что задача создаётся в `corpus/`.

## 9. Безопасность

- Никаких `eval`, никакого исполнения сгенерированного кода.
- Reviewer оценивает чтением, не запуском.
- API-токены не логируются.
- `.gitignore` исключает любые credentials/cache.

## 10. Ограничения и неустранимое

- Aккаунт Claude Code один — N команд жгут общий лимит, что даёт линейный множитель потребления, и это оптимально по таймеру → сам пользователь выбирает баланс через `session_limit_percent` и число команд.
- При `--print` режиме нет потокового вывода в реальном времени; пользователь видит логи постфактум.
- Дедупликация по hash, не семантическая — Planner может изредка генерить близкое-но-не-идентичное (приемлемо).
