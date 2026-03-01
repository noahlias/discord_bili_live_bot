#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"

IMAGE_NAME="${IMAGE_NAME:-discord-live-bot}"
IMAGE_TAG="${1:-slimcheck}"
OUT_DIR="${2:-dist}"
PLATFORM="linux/amd64"

IMAGE_REF="${IMAGE_NAME}:${IMAGE_TAG}"
SAFE_IMAGE_NAME="${IMAGE_NAME//\//_}"
SAFE_TAG="${IMAGE_TAG//\//_}"
SAFE_PLATFORM="${PLATFORM//\//_}"
OUTPUT_TAR="${OUT_DIR}/${SAFE_IMAGE_NAME}_${SAFE_TAG}_${SAFE_PLATFORM}.tar.gz"

mkdir -p "${OUT_DIR}"

echo "Building image ${IMAGE_REF} for ${PLATFORM}..."
docker buildx build \
  --platform "${PLATFORM}" \
  --load \
  -t "${IMAGE_REF}" \
  .

echo "Exporting image tarball to ${OUTPUT_TAR}..."
docker save "${IMAGE_REF}" | gzip > "${OUTPUT_TAR}"

echo
echo "Done."
echo "Tarball: ${OUTPUT_TAR}"
echo "Upload this file to server, then run:"
echo "  ./scripts/deploy_from_tar.sh ${OUTPUT_TAR} .env"
