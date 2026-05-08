#!/usr/bin/env bash
# taskforge — установка одной командой.
#
# Использование:
#   curl -fsSL https://raw.githubusercontent.com/ilyasmukiev/taskforge/main/install.sh | bash
#
# Или после клона:
#   bash install.sh

set -euo pipefail

SKILL_DIR="${HOME}/.claude/skills/taskforge"
DATA_DIR="${HOME}/.claude/skills-data/taskforge"
REPO_URL="https://github.com/ilyasmukiev/taskforge.git"

echo "─── taskforge installer ───"

# 1. Зависимости
command -v python3 >/dev/null || { echo "✗ нужен python3"; exit 1; }
command -v claude >/dev/null  || { echo "✗ нужен claude (Claude Code CLI)"; exit 1; }
command -v git >/dev/null     || { echo "✗ нужен git"; exit 1; }
echo "✓ python3, claude, git найдены"

# 2. Установить или обновить skill
if [[ -d "${SKILL_DIR}/.git" ]]; then
  echo "→ обновляю существующий skill в ${SKILL_DIR}"
  git -C "${SKILL_DIR}" pull --ff-only
elif [[ -d "${SKILL_DIR}" ]]; then
  echo "✗ ${SKILL_DIR} существует и не git-репо. Удали его руками и перезапусти."
  exit 1
else
  echo "→ клонирую ${REPO_URL} → ${SKILL_DIR}"
  mkdir -p "$(dirname "${SKILL_DIR}")"
  git clone --depth 1 "${REPO_URL}" "${SKILL_DIR}"
fi

# 3. chmod
chmod +x "${SKILL_DIR}/bin/taskforge"
echo "✓ ${SKILL_DIR}/bin/taskforge — executable"

# 4. Папка данных
mkdir -p "${DATA_DIR}/corpus" "${DATA_DIR}/state/teams" "${DATA_DIR}/logs"
echo "✓ ${DATA_DIR} готова"

# 5. Проверка
"${SKILL_DIR}/bin/taskforge" --version
echo
echo "Готово. В Claude Code запусти /taskforge или скажи 'запусти taskforge'."
echo "Без Claude:  python3 ${SKILL_DIR}/bin/taskforge wizard"
