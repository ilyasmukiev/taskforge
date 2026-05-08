---
name: taskforge
description: Длительная фоновая работа Claude Code — N параллельных команд (Planner→Executor→Reviewer) генерируют качественный корпус решённых задач, пока пользователь не за компьютером. Используй когда пользователь говорит "запусти taskforge", "/taskforge", "фоновая работа", "пусть работает пока я сплю", "набивай корпус задач", или просит длительный self-running режим с лимитами по времени/проценту сессии/проценту недели. Skill сам спрашивает у пользователя 8 параметров (модели для трёх ролей, число команд, длительность, два лимита, темы), сохраняет config и запускает фоновый оркестратор.
---

# taskforge — Skill manifest

## Когда срабатываешь

Триггеры (пользователь пишет / говорит):
- `/taskforge`, `taskforge`
- «запусти фоновую работу», «пусть работает пока я сплю»
- «набивай корпус задач», «генерируй решения в фоне»
- «продолжи taskforge», «taskforge resume»
- «останови taskforge», «taskforge stop»
- «taskforge status»

## Что ты делаешь

### Запуск нового цикла

1. **Не начинай ничего** до того, как соберёшь все 8 параметров.

2. **Задай пользователю 8 вопросов** через `AskUserQuestion` (или, если AskUserQuestion недоступен — построчно через текст с просьбой ответить):

   1. **Модель Planner-а** — кто придумывает задачи. Выбор: `opus` / `sonnet` / `haiku`. Default `opus`.
   2. **Модель Executor-а** — кто решает задачи. Выбор: `opus` / `sonnet` / `haiku`. Default `sonnet`.
   3. **Модель Reviewer-а** — кто оценивает решения. Выбор: `opus` / `sonnet` / `haiku`. Default `opus`.
   4. **Сколько команд параллельно** — целое число. Подсказка пользователю: «оптимально 3, потому что один аккаунт жжёт лимиты пропорционально».
   5. **Длительность** — формат `<число><h|m>`, например `5h`, `30m`. После истечения система выключится. Default `5h`.
   6. **Сессионный лимит, %** — абсолют от 5-часового окна Claude Code. По достижении этого процента — остановка. Default `50`.
   7. **Недельный лимит, %** — абсолют от недельного окна. По достижении — остановка. Default `50`. Семантика: **абсолют, не дельта** — если уже потрачено 49% и пользователь поставил 50, оркестратор почти сразу остановится. Если он хочет добавить именно X% — пусть посчитает: `текущий + желаемая_дельта`.
   8. **Темы** — multi-select из 10:
      - `code-block` — Писать код с нуля — один блок
      - `code-project` — Писать с нуля небольшой проект по плану
      - `bug-block` — Баг / оптимизация / синтаксис в одном блоке кода
      - `bug-project` — Баг / оптимизация / синтаксис в проекте
      - `web-search` — Веб-поиск релевантного / актуального ответа
      - `tools` — Работа с инструментами
      - `planning` — Планирование
      - `math-analysis` — Математический анализ
      - `higher-math` — Высшая математика
      - `logic` — Логика

      Default — все 10. Принимай также «все», «ALL», «*».

3. **Сохрани config** в JSON-файл:
   ```bash
   mkdir -p ~/.claude/skills-data/taskforge
   cat > ~/.claude/skills-data/taskforge/config.json <<EOF
   {
     "version": "0.1.0",
     "models": {"planner": "<X>", "executor": "<X>", "reviewer": "<X>"},
     "team_count": <N>,
     "duration_seconds": <SECONDS>,
     "session_limit_percent": <PCT>,
     "weekly_limit_percent": <PCT>,
     "topics": [<list>],
     "max_revise_iterations": 2
   }
   EOF
   ```

4. **Запусти оркестратор в фоне:**
   ```bash
   nohup python3 ~/.claude/skills/taskforge/bin/taskforge start \
     --config ~/.claude/skills-data/taskforge/config.json \
     > ~/.claude/skills-data/taskforge/logs/nohup.log 2>&1 &
   echo $!
   ```

5. **Сообщи пользователю:**
   - PID процесса (вывод `$!`)
   - Где смотреть логи: `~/.claude/skills-data/taskforge/logs/`
   - Где смотреть корпус: `~/.claude/skills-data/taskforge/corpus/`
   - Как остановить: `python3 ~/.claude/skills/taskforge/bin/taskforge stop`
   - Как смотреть статус: `python3 ~/.claude/skills/taskforge/bin/taskforge status`

### Status-запрос

Запусти `python3 ~/.claude/skills/taskforge/bin/taskforge status` и покажи вывод пользователю.

### Stop-запрос

Запусти `python3 ~/.claude/skills/taskforge/bin/taskforge stop`. Объясни, что graceful shutdown — текущие задачи доводятся до конца, на середине пишется чекпоинт, при следующем `resume` команды продолжат.

### Resume-запрос

Запусти `python3 ~/.claude/skills/taskforge/bin/taskforge resume --config ~/.claude/skills-data/taskforge/config.json`. Открытые чекпоинты будут разобраны первыми.

## Общие правила для тебя

- **Не запускай оркестратор без подтверждения пользователя** — сначала покажи итоговый JSON и спроси «ок?».
- **Не отвечай за пользователя на вопросы wizard-а.** Если пользователь сказал «делай как ты считаешь нужным» — используй дефолты, но покажи итог.
- **Если процесс уже запущен** (есть `~/.claude/skills-data/taskforge/state/orchestrator.pid` с живым PID) — не запускай второй, сообщи и предложи `stop` или `status`.
- **Корпус — приватные данные пользователя.** Никогда не пытайся коммитить `~/.claude/skills-data/taskforge/corpus/` в git.

## Документация

Полный дизайн: `~/.claude/skills/taskforge/docs/design.md`
