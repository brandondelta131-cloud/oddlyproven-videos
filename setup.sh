#!/usr/bin/env bash
# One-time setup for a fresh session: python deps + Kokoro voice models.
set -e
pip install --break-system-packages -q kokoro-onnx soundfile skia-python scipy numpy pillow 2>&1 | grep -v -i warning || true
export KOKORO_DIR=${KOKORO_DIR:-/tmp/kokoro}
mkdir -p "$KOKORO_DIR"
for f in kokoro-v1.0.onnx voices-v1.0.bin; do
  [ -s "$KOKORO_DIR/$f" ] || curl -sSL -o "$KOKORO_DIR/$f" "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/$f"
done
[ -d /usr/share/fonts/opentype/inter ] || echo "WARNING: Inter font missing (apt-get install -y fonts-inter)"
echo "setup ok; export KOKORO_DIR=$KOKORO_DIR"
