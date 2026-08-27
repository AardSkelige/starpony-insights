# Подготовка PATH для git-хуков. Подключается через `source`.
#
# Git, запущенный из IDE, открытой через Dock, наследует голый PATH
# (/usr/bin:/bin:/usr/sbin:/sbin) — ни node, ни gitleaks оттуда не видны,
# и хук падает с «command not found» вместо того, чтобы проверить код.
#
# Каталоги добавляются В КОНЕЦ: если инструмент уже доступен, побеждает он,
# а найденное здесь работает лишь как запасной вариант.

for _dir in \
  /opt/homebrew/opt/node@22/bin \
  /opt/homebrew/bin \
  /usr/local/bin
do
  [ -d "$_dir" ] && PATH="$PATH:$_dir"
done
unset _dir

# nvm держит бинарники в каталоге с номером версии, поэтому фиксированного
# пути нет — берём установленные версии, начиная со свежей.
if ! command -v node >/dev/null 2>&1; then
  for _dir in $(ls -d "$HOME"/.nvm/versions/node/*/bin 2>/dev/null | sort -r); do
    PATH="$PATH:$_dir"
  done
  unset _dir
fi

export PATH
