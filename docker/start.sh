#!/bin/sh
set -eu
mkdir -p "${DEMO_DATA:-/workspace/data}" "${XDG_RUNTIME_DIR:-/tmp/runtime}"
chmod 700 "${XDG_RUNTIME_DIR:-/tmp/runtime}"
touch "$HOME/.Xauthority"
VNC_RFB_PORT=${VNC_RFB_PORT:-5900}
NOVNC_LISTEN_PORT=${NOVNC_LISTEN_PORT:-6080}
X_SOCKET="/tmp/.X11-unix/X${DISPLAY#:}"
Xvfb "$DISPLAY" -screen 0 1440x900x24 -ac -nolisten tcp >/tmp/xvfb.log 2>&1 &
for i in 1 2 3 4 5 6 7 8 9 10; do [ -S "$X_SOCKET" ] && break; sleep 1; done
[ -S "$X_SOCKET" ] || { echo 'Xvfb no inició' >&2; cat /tmp/xvfb.log >&2; exit 1; }
openbox >/tmp/openbox.log 2>&1 &
x11vnc -display "$DISPLAY" -localhost -rfbport "$VNC_RFB_PORT" -shared -forever -nopw -quiet >/tmp/x11vnc.log 2>&1 &
websockify --web /usr/share/novnc "0.0.0.0:$NOVNC_LISTEN_PORT" "localhost:$VNC_RFB_PORT" >/tmp/novnc.log 2>&1 &
python scripts/generate_samples.py >/tmp/sample-refresh.log 2>&1
python -m app.server &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true' INT TERM EXIT
for i in 1 2 3 4 5 6 7 8 9 10; do
  if PORT="$PORT" python -c 'import os,urllib.request; urllib.request.urlopen("http://127.0.0.1:"+os.environ["PORT"]+"/api/health", timeout=2)' >/dev/null 2>&1; then break; fi
  sleep 1
done
chromium --no-sandbox --disable-dev-shm-usage --no-first-run \
  --user-data-dir=/tmp/rendicion-chromium --new-window "http://127.0.0.1:$PORT/" \
  >/tmp/chromium.log 2>&1 &
wait "$SERVER_PID"
