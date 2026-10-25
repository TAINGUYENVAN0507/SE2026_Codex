#!/bin/sh
# Smoke test cho image worker (AI-16). Chạy trong container, không cần mạng hay model:
#
#   docker run --rm -v "$PWD/infra/docker/smoke_worker.sh:/smoke.sh:ro" meeting-worker:cpu sh /smoke.sh
set -eu

echo "1. ffmpeg"
ffmpeg -hide_banner -version | head -1

echo "2. venv pipeline có runtime của model"
"$PIPELINE_PYTHON" -c "
import ctranslate2, faster_whisper, pyannote.audio, torch
assert '+cpu' in torch.__version__, torch.__version__
print('faster-whisper', faster_whisper.__version__, '| pyannote', pyannote.audio.__version__, '| torch', torch.__version__)
"

echo "3. venv backend import được worker, không có runtime của model"
python -c "
import importlib.util
import app.worker.runner  # noqa: F401
assert importlib.util.find_spec('faster_whisper') is None
assert importlib.util.find_spec('torch') is None
print('worker import ok')
"

echo "4. run_job từ venv backend, stage chạy bằng venv pipeline"
work=$(mktemp -d)
ffmpeg -nostdin -loglevel error -f lavfi -i "sine=frequency=440:duration=3" "$work/in.wav"
python - "$work" <<'PY'
import sys
from pathlib import Path

from meeting_pipeline.runner import run_job, stage_command
from meeting_pipeline.schemas import JobSpec, Stage

work = Path(sys.argv[1])
assert stage_command(Stage.ASR, work)[0] == "/app/pipeline/.venv/bin/python"
spec = JobSpec(meeting_id="smoke", job_id="smoke", audio_path=str(work / "in.wav"))
outcome = run_job(spec, workdir=work / "fake", backend="fake")
assert set(outcome.stage_status.values()) == {"succeeded"}, outcome.stage_status
print("fake pipeline: 6 stage ok")
PY

echo "5. preprocess thật (ffmpeg) trong container"
mkdir -p "$work/real"
python - "$work" <<'PY'
import sys
from pathlib import Path

from meeting_pipeline.schemas import JobSpec
from meeting_pipeline.workdir import write_job

work = Path(sys.argv[1])
write_job(work / "real", JobSpec(meeting_id="smoke", job_id="real", audio_path=str(work / "in.wav")))
PY
"$PIPELINE_PYTHON" -m meeting_pipeline run-stage preprocess --workdir "$work/real" --backend real >/dev/null
test -s "$work/real/audio.wav"
echo "preprocess thật ok"

echo "6. image không chứa secret hay dữ liệu"
test ! -e /app/.env
test ! -e /app/evaluation
test ! -e /app/reports
# Bỏ qua venv: vài thư viện (ví dụ scipy) kèm file .wav để tự test.
test -z "$(find /app -path '*/.venv' -prune -o \( -name '*.wav' -o -name '*.webm' -o -name '*.mp3' \) -print | head -1)"
test "$(id -u)" != "0"
echo "smoke test xong"
