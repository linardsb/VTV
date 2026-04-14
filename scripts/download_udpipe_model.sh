#!/usr/bin/env bash
# Download the Latvian UDPipe 2.5 model for the KB-2 lemmatizer.
#
# Model source: LINDAT/UFAL CUNI (UD 2.5, Latvian LVTB treebank).
# The artifact (~50 MB) is excluded from git via .gitignore.
set -euo pipefail

MODEL_DIR="${MODEL_DIR:-models}"
MODEL_FILE="${MODEL_DIR}/latvian-ud-2.5.udpipe"
MODEL_URL="https://lindat.mff.cuni.cz/repository/xmlui/bitstream/handle/11234/1-3131/latvian-lvtb-ud-2.5-191206.udpipe"

mkdir -p "${MODEL_DIR}"

if [[ -f "${MODEL_FILE}" ]]; then
  echo "[udpipe] Model already present at ${MODEL_FILE} — skipping."
  exit 0
fi

echo "[udpipe] Downloading Latvian UDPipe 2.5 model to ${MODEL_FILE}..."
curl -fL --retry 3 --retry-delay 2 -o "${MODEL_FILE}" "${MODEL_URL}"
echo "[udpipe] Done."
