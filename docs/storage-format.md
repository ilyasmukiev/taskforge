# Формат хранения taskforge

Полное описание того, как taskforge организует данные на диске. Этот документ — справочник: где что лежит, в каком формате, как читать, искать и переносить.

## 1. Корневая папка

Все запуски пишут в **одну глобальную** папку:

| ОС | Путь |
|----|------|
| macOS / Linux | `~/.claude/skills-data/taskforge/` |
| Windows | `%USERPROFILE%\.claude\skills-data\taskforge\` |

Папка **не сбрасывается** между запусками — корпус только пополняется. Удалять её не стоит, если хочешь сохранить накопленный материал.

## 2. Дерево

```
~/.claude/skills-data/taskforge/
├── corpus/
│   └── <topic-slug>/                          # одна папка на тему
│       └── <YYYY-MM-DD-task-NNNN>/            # одна папка на задачу
│           ├── task.md                        # условие
│           ├── solution-v1.md                 # решение, попытка 1
│           ├── review-v1.md                   # оценка, попытка 1
│           ├── solution-v2.md                 # переделка, попытка 2
│           ├── review-v2.md                   # ...
│           ├── solution.md                    # копия финальной (= последний v)
│           ├── review.md                      # копия финального review
│           ├── thinking/                      # нити мысли каждого агента
│           │   ├── planner.md
│           │   ├── executor-v1.md
│           │   ├── reviewer-v1.md
│           │   ├── executor-v2.md
│           │   └── reviewer-v2.md
│           ├── sessions/                      # копии локальных чатов Claude Code
│           │   ├── planner.jsonl
│           │   ├── executor-v1.jsonl
│           │   ├── reviewer-v1.jsonl
│           │   ├── executor-v2.jsonl
│           │   └── reviewer-v2.jsonl
│           ├── code/                          # файлы кода (если кодовая тема)
│           ├── agents.json                    # манифест задачи
│           ├── meta.json                      # сводка задачи
│           └── checkpoint.json                # ТОЛЬКО если задача не доделана
├── index.json                                  # индекс всех завершённых задач
├── config.json                                 # параметры последнего запуска
├── state/
│   ├── runtime.json                           # текущее состояние оркестратора
│   ├── orchestrator.pid                       # PID работающего процесса
│   ├── stop.flag                              # graceful stop signal (если активен)
│   └── teams/<team-id>/status.json            # статус каждой команды
└── logs/run-YYYY-MM-DD.log                    # текстовый лог запусков
```

**Примеры реальных путей:**
- `corpus/code-block/2026-05-08-task-0042/` — 42-я задача темы «один блок кода» от 8 мая
- `corpus/math-analysis/2026-05-09-task-0001/` — первая задача темы «мат-анализ» 9 мая
- `corpus/logic/2026-05-08-task-0017/thinking/reviewer-v2.md` — мышление Reviewer-а во второй итерации

## 3. Формат каждого файла

### `task.md` — условие задачи (Markdown)

Что записал Planner. Стандартная структура:

```markdown
# <Краткий заголовок>

## Контекст
<1–3 абзаца>

## Требования
- ...

## Приёмочные критерии
- ...

## Подсказки (опционально)
- ...
```

Кодировка UTF-8. Без BOM.

### `solution-v{N}.md` и `solution.md` — решение Executor-а

Markdown. Финальная пара (`solution.md`/`review.md`) = последний `v{N}`.

```markdown
# Решение

## Подход
<...>

## Реализация
<код в блоках ```language>

## Проверка
<...>
```

### `review-v{N}.md` и `review.md` — оценка Reviewer-а

Начинается **обязательно** с YAML-блока `verdict`:

```markdown
---
verdict: pass
---

# Review

## Сильные стороны
- ...

## Замечания
- ...

## Что переделать  (только если verdict=revise)
- ...

## Почему отброшено  (только если verdict=discard)
- ...

## Итог
<1–3 предложения>
```

`verdict` — одно из трёх:
- `pass` — решение принято
- `revise` — Executor переделывает с фидбеком (max 2 раза)
- `discard` — задача / решение принципиально дефектные, идём дальше

### `meta.json` — сводка задачи

```json
{
  "id": "code-block-2026-05-08-task-0001",
  "topic": "code-block",
  "title": "Реализовать LRU кэш на Python",
  "condition_hash": "b94d27b9934d3e08",
  "models": {"planner": "opus", "executor": "sonnet", "reviewer": "opus"},
  "verdict": "pass",
  "iterations": 2,
  "started_at": "2026-05-08T20:55:01Z",
  "finished_at": "2026-05-08T21:02:43Z",
  "team_id": "team-2"
}
```

### `agents.json` — манифест ⭐ главный файл для систематизации

Связывает каждую агентскую сессию с её артефактами и даёт готовую команду открыть чат:

```json
{
  "task_id": "code-block-2026-05-08-task-0001",
  "version": "0.1.0",
  "agents": [
    {
      "role": "planner",
      "iteration": null,
      "session_id": "01234567-89ab-cdef-0123-456789abcdef",
      "session_name": "taskforge:planner:code-block:attempt-1",
      "model": "opus",
      "effort": "high",
      "started_at": "2026-05-08T20:55:01Z",
      "finished_at": "2026-05-08T20:55:32Z",
      "duration_ms": 31420,
      "cost_usd": 0.0143,
      "input_tokens": 9,
      "output_tokens": 312,
      "output_file": "task.md",
      "session_log": "sessions/planner.jsonl",
      "session_log_source": "/Users/nnn/.claude/projects/-Users-nnn--claude-skills-taskforge/01234567-89ab-cdef-0123-456789abcdef.jsonl",
      "thinking_file": "thinking/planner.md",
      "resume_command": "claude --resume 01234567-89ab-cdef-0123-456789abcdef"
    },
    {
      "role": "executor",
      "iteration": 1,
      "session_id": "...",
      "session_name": "taskforge:executor:v1:code-block:2026-05-08-task-0001",
      "model": "sonnet",
      "output_file": "solution-v1.md",
      "session_log": "sessions/executor-v1.jsonl",
      "thinking_file": "thinking/executor-v1.md",
      "resume_command": "claude --resume ..."
    }
  ]
}
```

**Поля:**

| поле | тип | что значит |
|------|-----|------------|
| `role` | string | `planner` / `executor` / `reviewer` |
| `iteration` | int / null | номер итерации (1, 2, ...). Для Planner — `null` |
| `session_id` | UUID | UUID сессии Claude Code |
| `session_name` | string | человекочитаемое имя — видно в `claude /resume` picker |
| `model` | string | `opus` / `sonnet` / `haiku` |
| `effort` | string | `none` / `low` / `medium` / `high` / `xhigh` / `max` |
| `started_at`, `finished_at` | ISO 8601 UTC | таймстемпы |
| `duration_ms` | int | длительность вызова в мс |
| `cost_usd` | float | стоимость вызова |
| `input_tokens`, `output_tokens` | int | расход токенов |
| `output_file` | string | относительный путь к Markdown с ответом |
| `session_log` | string | относительный путь к копии JSONL внутри задачи |
| `session_log_source` | string | оригинальный путь в `~/.claude/projects/` |
| `thinking_file` | string / null | путь к Markdown с thinking, `null` если не было |
| `resume_command` | string | готовая команда `claude --resume <UUID>` |

### `thinking/<role>-v{N}.md` — нити мысли

Для каждого агентского вызова (если был thinking — `effort` ≠ `none` и модель его вернула) генерируется Markdown с заголовком-метаданными и текстом размышлений:

```markdown
# Reviewer — итерация 2

- session_id: `7f3a9c81-...`
- session_name: `taskforge:reviewer:v2:logic:2026-05-08-task-0042`
- model: `opus`
- effort: `high`
- started: 2026-05-08T21:00:12Z
- finished: 2026-05-08T21:01:48Z
- duration_ms: 96214
- cost_usd: 0.0421
- input_tokens: 1547
- output_tokens: 1108

---

<извлечённый текст thinking>

---

<возможно второй блок thinking, если их было несколько>
```

### `sessions/<role>-v{N}.jsonl` — копия чата Claude Code

JSONL-файл, скопированный из `~/.claude/projects/<slug>/<UUID>.jsonl`. Это **полный** локальный лог сессии: системный промпт, user-сообщение, все assistant-content-блоки (thinking + text). Каждая строка — JSON.

Ключевые типы записей:
- `custom-title`, `agent-name` — имя сессии (то самое `taskforge:planner:...`)
- `attachment` — служебные attachments (hooks, system reminders)
- `user` — наше сообщение Planner-у/Executor-у/Reviewer-у
- `assistant` — ответ модели; `message.content` — массив блоков:
  - `{"type": "thinking", "thinking": "..."}` — рассуждение
  - `{"type": "text", "text": "..."}` — финальный ответ
- `last-prompt` — закрывающая запись

### `checkpoint.json` — точка восстановления

Появляется ТОЛЬКО если задача не доделана (graceful stop / лимит). Содержит:

```json
{
  "task_id": "...",
  "topic": "...",
  "phase": "after_executor",   // before_executor | after_executor
  "iteration": 1,               // текущая итерация
  "task_md": "...",             // полное условие
  "solution_md": "...",         // последнее решение (если phase=after_executor)
  "review_md": "...",           // последний review (если был)
  "title": "...",
  "condition_hash": "...",
  "started_at": "...",
  "checkpoint_at": "...",
  "agents_log": [...]           // массив agent-записей до checkpoint'а
}
```

При `taskforge resume` команда находит этот файл, восстанавливает состояние и продолжает с нужной фазы. После успешного завершения задачи `checkpoint.json` удаляется.

### `index.json` — индекс всех завершённых задач

Массив сжатых записей для быстрого поиска и аналитики:

```json
[
  {
    "id": "code-block-2026-05-08-task-0001",
    "topic": "code-block",
    "title": "Реализовать LRU кэш на Python",
    "condition_hash": "b94d27b9934d3e08",
    "verdict": "pass",
    "path": "corpus/code-block/2026-05-08-task-0001",
    "finished_at": "2026-05-08T21:02:43Z"
  }
]
```

Атомарная запись через `os.replace` — файл всегда консистентен.

### `state/runtime.json` — состояние оркестратора

Обновляется каждые 5 секунд:

```json
{
  "pid": 12345,
  "started_at": 1746737701.5,
  "now": 1746738901.2,
  "should_stop": false,
  "five_hour_pct": 22.5,
  "weekly_pct": 47.1,
  "monthly_pct": 0,
  "elapsed": 1199.7,
  "duration_seconds": 18000,
  "reason": "running"
}
```

### `state/teams/<id>/status.json` — статус команды

Обновляется командой между фазами:

```json
{
  "team_id": "team-2",
  "phase": "executor",
  "topic": "logic",
  "task_id": "logic-2026-05-08-task-0042",
  "last_heartbeat": "2026-05-08T21:00:14Z"
}
```

Фазы: `idle`, `planning`, `executor`, `reviewer`, `error`, `done`.

### `config.json` — конфигурация запуска

То же, что `DEFAULT_CONFIG` в `bin/taskforge`, заполненное wizard-ом. Например:

```json
{
  "version": "0.1.0",
  "models": {"planner": "opus", "executor": "sonnet", "reviewer": "opus"},
  "effort": {"planner": "high", "executor": "high", "reviewer": "high"},
  "team_count": 3,
  "duration_seconds": 18000,
  "session_limit_percent": 50,
  "weekly_limit_percent": 50,
  "topics": ["code-block", "logic", "math-analysis", "..."],
  "max_revise_iterations": 2,
  "started_at": "2026-05-08T20:55:00Z"
}
```

## 4. Поиск и систематизация (jq примеры)

```bash
DATA=~/.claude/skills-data/taskforge

# Все pass-задачи по теме logic
jq '.[] | select(.topic=="logic" and .verdict=="pass")' $DATA/index.json

# Сводка по темам и вердиктам
jq -r '.[] | "\(.topic)\t\(.verdict)"' $DATA/index.json | sort | uniq -c

# Топ-5 самых дорогих задач
for d in $DATA/corpus/*/*/agents.json; do
  total=$(jq '[.agents[].cost_usd] | add' "$d")
  echo "$total $(dirname $d)"
done | sort -rn | head -5

# Все resume-команды для задач за сегодня
jq -r ".agents[] | .resume_command" $DATA/corpus/*/2026-05-08-*/agents.json

# Сколько токенов я потратил всего
jq -s '[.[].agents[] | .input_tokens + .output_tokens] | add' $DATA/corpus/*/*/agents.json

# Поиск по содержимому решений
grep -rli "OrderedDict" $DATA/corpus/

# Все разы, когда Reviewer попросил revise (читая v1 reviews)
grep -l "verdict: revise" $DATA/corpus/*/*/review-v1.md
```

## 5. Восстановление после потерь данных

| Что потерялось | Чем восстанавливается |
|---------------|----------------------|
| `~/.claude/projects/<slug>/<UUID>.jsonl` (Claude Code очистил сессии) | `corpus/<task>/sessions/<role>-vN.jsonl` — копии taskforge сделал сразу после вызова |
| `corpus/<task>/solution.md` (финальный) | `corpus/<task>/solution-v{N}.md` (последний v) — это то же самое |
| `corpus/<task>/thinking/<role>-vN.md` | Распарсить заново из `corpus/<task>/sessions/<role>-vN.jsonl` (формат описан выше) |
| `index.json` | Можно собрать заново обходом `corpus/*/*/meta.json` |
| `config.json` | Не критично — нужен только для следующего запуска, можно пересоздать через `taskforge wizard` |

## 6. Перенос на другую машину

Корпус — обычные файлы UTF-8, без бинарников и абсолютных ссылок:

```bash
# С исходной машины
tar -czf taskforge-corpus.tar.gz -C ~/.claude/skills-data/taskforge corpus index.json

# На новой
tar -xzf taskforge-corpus.tar.gz -C ~/.claude/skills-data/taskforge/
```

Поле `session_log_source` в `agents.json` содержит абсолютный путь оригинального JSONL — он будет невалиден на новой машине, но **`session_log` (`sessions/<role>-vN.jsonl`)** относительный и работает.

`resume_command` (`claude --resume <UUID>`) **не сработает** на новой машине, потому что Claude Code не знает про эти session_id. Но содержимое JSONL читается любым редактором.

## 7. Совместимость

- Все JSON — UTF-8, без BOM, через `os.replace` (атомарная запись).
- Все Markdown — UTF-8, без BOM, LF переводы строк (на Windows тоже LF).
- `condition_hash` — sha256, первые 16 hex-символов от нормализованного условия (lower, trim, multi-space → single).
- `session_id` — стандартный UUID v4.
- Имена папок — ASCII (slug темы + дата ISO + номер).
