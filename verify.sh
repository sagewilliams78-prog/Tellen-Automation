#!/bin/bash
# Full regression check: world data integrity, studio sandbox/logic, and a
# live boot of the actual server with every route hit once.
#
# Run this after touching hq/, studio.py, or dashboard_server.py, before
# trusting the change. Nothing here replaces looking at it -- it just makes
# sure the things that used to only fail silently now fail loudly first.
set -e
cd "$(dirname "$0")"

echo "════════════════════════════════════════════════════════════"
echo "1/3  World data (hq/verify.mjs)"
echo "════════════════════════════════════════════════════════════"
node hq/verify.mjs

echo "════════════════════════════════════════════════════════════"
echo "2/3  Studio sandbox + logic (verify_studio.py)"
echo "════════════════════════════════════════════════════════════"
python3 verify_studio.py

echo "════════════════════════════════════════════════════════════"
echo "3/3  Live boot: every route responds"
echo "════════════════════════════════════════════════════════════"
python3 -m py_compile dashboard_server.py studio.py town_assets.py gen_town_assets.py
echo "  ✓ syntax OK"

PORT_WAS_UP=$(lsof -ti:8420 || true)
[ -n "$PORT_WAS_UP" ] && kill $PORT_WAS_UP 2>/dev/null
sleep 1
python3 dashboard_server.py > /tmp/verify_boot.log 2>&1 &
SERVER_PID=$!
sleep 2

FAIL=0
for route in / /town /hq/ /api/status /api/studio /api/security; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8420${route}")
  if [ "$CODE" = "200" ]; then
    echo "  ✓ ${route} -> ${CODE}"
  else
    echo "  ✗ ${route} -> ${CODE}"
    FAIL=1
  fi
done

# no unreplaced Python-side template tokens in the HTML the browser gets
LEFTOVER=$(curl -s http://localhost:8420/town | grep -oE '__[A-Z_0-9]+__' | sort -u || true)
if [ -n "$LEFTOVER" ]; then
  echo "  ✗ leftover template token(s) in /town: $LEFTOVER"
  FAIL=1
else
  echo "  ✓ no leftover template tokens in /town"
fi

kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null || true

if [ "$FAIL" = "1" ]; then
  echo ""
  echo "FAIL"
  exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "ALL PASS"
echo "════════════════════════════════════════════════════════════"
