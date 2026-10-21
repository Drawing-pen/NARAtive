#!/bin/sh
set -e

CKPT="$MODEL_DIR/model_best.pt"
if [ ! -f "$CKPT" ]; then
  if [ -n "$MODEL_URL" ]; then
    echo "[narative] model_best.pt belum ada, mengunduh dari $MODEL_URL (sekitar 1,1 GB) ..."
    mkdir -p "$MODEL_DIR"
    python - <<PY
import os, sys, urllib.request
url, dest = os.environ["MODEL_URL"], os.environ["MODEL_DIR"] + "/model_best.pt"
tmp = dest + ".part"
try:
    urllib.request.urlretrieve(url, tmp)
    os.replace(tmp, dest)
except Exception as e:
    print(f"[narative] GAGAL mengunduh model: {e}", file=sys.stderr)
PY
  else
    echo "[narative] PERINGATAN: model/model_best.pt belum ada. Taruh filenya di folder model/ (analisis baru jalan setelah itu)."
  fi
fi

python -m alembic upgrade head
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
