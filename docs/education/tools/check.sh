#!/usr/bin/env bash
# Layout check for one or more decks. Prints, per slide, "ok" or the overflow problems.
# Usage: tools/check.sh 03-repo-map.html [more.html ...]
#        tools/check.sh --shots 03-repo-map.html   # also writes /tmp/edu-shots/<deck>-<n>.png
set -euo pipefail
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
cd "$(dirname "$0")/.."
shots=0; [ "${1:-}" = "--shots" ] && { shots=1; shift; }
for f in "$@"; do
  echo "== $f"
  "$CHROME" --headless=new --disable-gpu --window-size=1280,720 --dump-dom "file://$PWD/$f?check" 2>/dev/null \
    | sed -n '/<pre id="check-result">/,/<\/pre>/p' | sed -e 's/.*<pre id="check-result">//' -e 's/<\/pre>.*//' -e 's/&lt;/</g;s/&gt;/>/g;s/&amp;/\&/g'
  if [ $shots = 1 ]; then
    mkdir -p /tmp/edu-shots
    n=$(grep -c '<section class="slide' "$f")
    for i in $(seq 1 "$n"); do
      "$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size=1280,720 \
        --screenshot="/tmp/edu-shots/${f%.html}-$i.png" "file://$PWD/$f?all#/$i" 2>/dev/null
    done
    echo "screenshots: /tmp/edu-shots/${f%.html}-*.png"
  fi
done
