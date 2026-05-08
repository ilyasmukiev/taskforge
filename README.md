# taskforge

> **Длительная фоновая работа Claude Code** — N команд параллельно генерируют качественный корпус решённых задач, пока ты не за компьютером.

[Russian](#russian) · [English](#english)

---

## Russian

### Что это

Skill для Claude Code, который запускает **фоновую мельницу решений**. Ты говоришь Claude `/taskforge`, отвечаешь на 8 вопросов мастера настройки, и дальше система **сама** до N часов параллельно гонит цикл `Planner → Executor → Reviewer`:

- **Planner** придумывает задачу в выбранной теме (10 тем: код, баги, веб-поиск, мат-анализ, логика и др.).
- **Executor** решает её.
- **Reviewer** оценивает строго: `pass` / `revise` / `discard`. При `revise` — Executor переделывает (до 2 раз).

Все решения копятся в `~/.claude/skills-data/taskforge/corpus/` — структурированно, с метаданными. Между запусками корпус не пропадает.

### Зачем

- Пока ты не за компьютером, лимит подписки Claude Code не пропадает зря — система превращает его в **полезный архив решений**, который потом можно листать или искать.
- **Качество > количество**: каждое решение проверяется отдельным агентом. Плохое — на доработку. Принципиально дефектное — отбрасывается.
- Никаких внешних API-ключей: используется твоя текущая подписка Claude Code (через `claude` CLI).

### Установка

**macOS / Linux:**
```bash
git clone https://github.com/ilyasmukiev/taskforge.git ~/.claude/skills/taskforge
chmod +x ~/.claude/skills/taskforge/bin/taskforge
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/ilyasmukiev/taskforge.git "$env:USERPROFILE\.claude\skills\taskforge"
# chmod не нужен — Python вызывается явно.
```

После этого Claude видит skill `taskforge` и реагирует на триггеры.

### Запуск

В чате Claude Code:
```
/taskforge
```
или просто:
```
запусти taskforge
```

Claude задаст 8 вопросов:

| # | Параметр | Default |
|---|----------|---------|
| 1 | Модель Planner-а (`opus`/`sonnet`/`haiku`) | `opus` |
| 2 | Модель Executor-а | `sonnet` |
| 3 | Модель Reviewer-а | `opus` |
| 4 | Сколько команд параллельно | `3` |
| 5 | Длительность (`5h`, `30m`, `90s`) | `5h` |
| 6 | Сессионный лимит, % абсолют | `50` |
| 7 | Недельный лимит, % абсолют | `50` |
| 8 | Темы (через запятую или `все`) | все 10 |

После подтверждения оркестратор уходит в фон (через `nohup`), Claude сообщает PID. Дальше можно закрывать чат — работа продолжается.

### Управление

```bash
# Проверить состояние
python3 ~/.claude/skills/taskforge/bin/taskforge status

# Остановить (graceful: текущие задачи дочитываются, потом чекпоинт)
python3 ~/.claude/skills/taskforge/bin/taskforge stop

# Продолжить с того места, где остановились (поднимет чекпоинты)
python3 ~/.claude/skills/taskforge/bin/taskforge resume \
  --config ~/.claude/skills-data/taskforge/config.json

# Запуск без Claude (например по cron):
python3 ~/.claude/skills/taskforge/bin/taskforge wizard
```

### Что в корпусе

Все запуски пишут в **одну** глобальную папку `~/.claude/skills-data/taskforge/` — корпус только пополняется и не сбрасывается.

```
~/.claude/skills-data/taskforge/
├── corpus/
│   └── code-block/
│       └── 2026-05-08-task-0001/
│           ├── task.md              # условие от Planner (один файл на задачу)
│           ├── solution-v1.md       # первая попытка Executor
│           ├── review-v1.md         # вердикт revise + замечания
│           ├── solution-v2.md       # переделка с учётом фидбека
│           ├── review-v2.md         # финальный pass
│           ├── solution.md          # копия финальной (= solution-v2.md)
│           ├── review.md            # копия финального review
│           ├── thinking/            # ⭐ нити мысли каждого агента
│           │   ├── planner.md       # как Planner придумывал задачу
│           │   ├── executor-v1.md   # как Executor решал в 1-й итерации
│           │   ├── reviewer-v1.md   # как Reviewer оценивал
│           │   ├── executor-v2.md
│           │   └── reviewer-v2.md
│           ├── sessions/            # ⭐ полные локальные чаты Claude Code
│           │   ├── planner.jsonl
│           │   ├── executor-v1.jsonl
│           │   ├── reviewer-v1.jsonl
│           │   ├── executor-v2.jsonl
│           │   └── reviewer-v2.jsonl
│           ├── agents.json          # ⭐ манифест: роль → session_id, модель, время, токены, стоимость, resume_command
│           ├── code/                # файлы с кодом, если кодовая тема
│           ├── meta.json            # модели, время, итерации, вердикт
│           └── checkpoint.json      # ТОЛЬКО если задача не доделана
├── index.json                        # сводный индекс всех задач
├── config.json                       # параметры последнего запуска
├── state/
│   ├── runtime.json                 # текущее состояние оркестратора
│   ├── orchestrator.pid             # PID работающего процесса
│   ├── stop.flag                    # флаг graceful stop (если активен)
│   └── teams/<id>/status.json       # статус каждой команды
└── logs/run-2026-05-08.log
```

**Что нового и важного:**

- **Полный диалог между агентами:** все итерации Executor⇄Reviewer лежат отдельными файлами `solution-v{N}.md` / `review-v{N}.md`. `solution.md` и `review.md` — финальная пара для быстрого доступа.
- **Нити мысли (`thinking/`):** при `effort: high` (default) каждый агент возвращает блок thinking — внутри `thinking/<role>-v{N}.md` лежит как агент рассуждал. Полезно когда «решение почти то, но я бы вот тут переделал» — видишь почему модель пошла именно этим путём.
- **Локальные чаты Claude Code (`sessions/`):** оригинальный JSONL-лог сессии каждого агента (Planner, Executor v1/v2, Reviewer v1/v2). Можно открыть через любой текстовый редактор — он содержит полный диалог.
- **`agents.json`:** манифест задачи — для каждого агента указан `session_id`, `session_name` (видно в `claude /resume` picker'е), `resume_command` (готовая команда `claude --resume <UUID>`), модель, токены, стоимость и пути к артефактам.

### Открыть локально чат любого агента

В `agents.json` рядом с каждым агентом лежит `resume_command` — например:
```bash
claude --resume 0308bdf3-042a-43ff-b2bd-48194dac549e
```
Открывается тот самый чат с Planner-ом / Executor-ом / Reviewer-ом, можно дописать сообщение и продолжить руками. Если задача почти то, что нужно — открываешь чат Executor-а и допиливаешь.

Альтернатива — `claude /resume` без аргументов: в picker'е сессии видны по имени `taskforge:planner:code-block:attempt-1`, `taskforge:executor:v1:code-block:2026-05-08-task-0001` и т.д.

### Стоп-условия

Срабатывает любое первым (OR-логика):
1. **Таймер** — прошла указанная длительность.
2. **Сессионный лимит** — `fiveHourPercent` ≥ заданного `%`.
3. **Недельный лимит** — `weeklyPercent` ≥ заданного `%`.
4. **`taskforge stop`** или `Ctrl+C`.

При остановке: команды дочитывают текущий шаг, в незавершённой задаче пишется `checkpoint.json`. При `resume` — команды первым делом разбирают чекпоинты.

### Где берутся проценты лимитов

Из Anthropic OAuth API (`api.anthropic.com/api/oauth/usage`). Для авторизации читается access token из macOS Keychain (`Claude Code-credentials`) или из `~/.claude/.credentials.json`. Если у тебя установлен **OMC HUD**, taskforge читает его кеш — это быстрее. На Linux/Windows работает только через файл credentials.

### Платформы

| Часть | macOS | Linux | Windows |
|------|------|------|------|
| Skill виден Claude Code | ✅ | ✅ | ✅ |
| Wizard и оркестратор | ✅ | ✅ | ✅ |
| `claude -p` subprocess | ✅ | ✅ | ✅ (требуется Claude Code CLI) |
| Чтение лимитов из Keychain | ✅ | — | — |
| Чтение лимитов из `.credentials.json` | ✅ | ✅ | ✅ |
| Чтение OMC-кеша | ✅ | ✅ | ✅ |
| `taskforge stop` (graceful + чекпоинт) | ✅ | ✅ | ✅ (через файл-флаг) |
| Запуск в фоне | `nohup ... &` | `nohup ... &` | `Start-Process -WindowStyle Hidden` |
| `install.sh` | ✅ | ✅ | требует Git Bash или WSL |

Stop работает кросс-платформенно через файл-флаг `state/stop.flag` (оркестратор опрашивает его каждые 5 сек). На macOS/Linux дополнительно шлётся `SIGTERM` — обычно реакция мгновенная.

### Безопасность

- Сгенерированный код **не запускается**. Reviewer оценивает чтением.
- Никаких внешних webhook'ов, телеметрии, отправки данных.
- Корпус — **локальный**, никогда не попадает в git репо taskforge.

### Кастомизация

- Промпты Planner-а / Executor-а / Reviewer-а — в `prompts/*.md`. Можно править под себя.
- Список тем — в `bin/taskforge` (константа `TOPICS`). Можно дополнять.
- Таймаут одного `claude -p` вызова — env var `TASKFORGE_CLAUDE_TIMEOUT` (default 900 сек).
- Путь к `claude` бинарнику — env var `TASKFORGE_CLAUDE_BIN`.

### Лицензия

MIT. См. `LICENSE`.

---

## English

### What it is

A Claude Code skill that runs a **background solution mill**. You type `/taskforge`, answer 8 wizard questions, and the system spins up to N hours of parallel `Planner → Executor → Reviewer` cycles:

- **Planner** invents a task in a chosen topic (10 topics: code blocks, bugs, web search, calculus, logic, etc.).
- **Executor** solves it.
- **Reviewer** grades strictly: `pass` / `revise` / `discard`. On `revise`, Executor reworks (up to 2 retries).

All solutions accumulate in `~/.claude/skills-data/taskforge/corpus/` — structured, with metadata, persistent across runs.

### Why

- While you're away, your Claude Code subscription quota turns into a **useful archive of solved problems** — browsable, searchable.
- **Quality over quantity**: every solution is reviewed by a separate agent; bad ones go back for rework, fundamentally broken ones are discarded.
- No external API keys: uses your existing Claude Code subscription via the `claude` CLI.

### Install

**macOS / Linux:**
```bash
git clone https://github.com/ilyasmukiev/taskforge.git ~/.claude/skills/taskforge
chmod +x ~/.claude/skills/taskforge/bin/taskforge
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/ilyasmukiev/taskforge.git "$env:USERPROFILE\.claude\skills\taskforge"
```

Restart Claude Code; the skill is auto-discovered.

### Run

In Claude Code chat:
```
/taskforge
```

Answer 8 questions (planner/executor/reviewer models, parallel teams, duration, session %, weekly %, topics). The orchestrator detaches via `nohup`. You can close the chat; work continues in the background.

### Control

```bash
~/.claude/skills/taskforge/bin/taskforge status
~/.claude/skills/taskforge/bin/taskforge stop      # graceful + checkpoint
~/.claude/skills/taskforge/bin/taskforge resume    # continue from checkpoints
~/.claude/skills/taskforge/bin/taskforge wizard    # standalone (no Claude)
```

### Stop conditions (OR-logic)

1. Timer expires.
2. `fiveHourPercent ≥ session_limit_percent`.
3. `weeklyPercent ≥ weekly_limit_percent`.
4. `taskforge stop` or `Ctrl+C`.

Graceful shutdown: in-progress steps finish, mid-task progress is checkpointed; `resume` picks up.

### Limit data source

`api.anthropic.com/api/oauth/usage` with token from macOS Keychain (`Claude Code-credentials`) or `~/.claude/.credentials.json`. If OMC HUD is installed, its cache is used (faster).

### Cross-platform notes

| Part | macOS | Linux | Windows |
|------|-------|-------|---------|
| Skill discovery, wizard, orchestrator | ✅ | ✅ | ✅ |
| `claude -p` subprocess | ✅ | ✅ | ✅ (Claude Code CLI required) |
| Keychain credentials | ✅ | — | — |
| File credentials (`~/.claude/.credentials.json`) | ✅ | ✅ | ✅ |
| `taskforge stop` (graceful + checkpoint) | ✅ | ✅ | ✅ via `state/stop.flag` |
| Background launch | `nohup ... &` | `nohup ... &` | `Start-Process -WindowStyle Hidden` |
| `install.sh` | ✅ | ✅ | needs Git Bash or WSL |

Stop is cross-platform via a `state/stop.flag` file (orchestrator polls every 5 s). On macOS/Linux a SIGTERM is also sent for instant reaction.

### License

MIT.
