#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CONFIG_FILE="${1:-${PROJECT_DIR}/deploy/server.conf}"
if [ ! -f "${CONFIG_FILE}" ]; then
  echo "Config file not found: ${CONFIG_FILE}" >&2
  echo "Create it from: deploy/server.conf.example" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${CONFIG_FILE}"

require_var() {
  local name="$1"
  local value="${!name:-}"
  if [ -z "${value}" ]; then
    echo "Missing required config value: ${name}" >&2
    exit 1
  fi
}

require_var SSH_USER
require_var SSH_HOST

SSH_PORT="${SSH_PORT:-22}"
IMAGE_NAME="${IMAGE_NAME:-discord-live-bot}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
TAR_OUT_DIR="${TAR_OUT_DIR:-dist}"
ENV_FILE_LOCAL="${ENV_FILE_LOCAL:-.env}"
REMOTE_DIR="${REMOTE_DIR:-/opt/discord-live-bot}"
REMOTE_ENV_FILE="${REMOTE_ENV_FILE:-${REMOTE_DIR}/.env}"
REMOTE_TAR_DIR="${REMOTE_TAR_DIR:-${REMOTE_DIR}/dist}"
REMOTE_DATA_DIR="${REMOTE_DATA_DIR:-${REMOTE_DIR}/data}"
CONTAINER_NAME="${CONTAINER_NAME:-discord-live-bot}"

if [[ "${ENV_FILE_LOCAL}" != /* ]]; then
  ENV_FILE_LOCAL="${PROJECT_DIR}/${ENV_FILE_LOCAL}"
fi

if [ ! -f "${ENV_FILE_LOCAL}" ]; then
  echo "Env file not found: ${ENV_FILE_LOCAL}" >&2
  exit 1
fi

SAFE_IMAGE_NAME="${IMAGE_NAME//\//_}"
SAFE_TAG="${IMAGE_TAG//\//_}"
LOCAL_TAR="${PROJECT_DIR}/${TAR_OUT_DIR}/${SAFE_IMAGE_NAME}_${SAFE_TAG}_linux_amd64.tar.gz"
REMOTE_TAR="${REMOTE_TAR_DIR}/$(basename "${LOCAL_TAR}")"
REMOTE_DEPLOY_SCRIPT="${REMOTE_DIR}/deploy_from_tar.sh"

echo "Building linux/amd64 image tar..."
IMAGE_NAME="${IMAGE_NAME}" "${PROJECT_DIR}/scripts/build_linux_amd64_tar.sh" "${IMAGE_TAG}" "${TAR_OUT_DIR}"

if [ ! -f "${LOCAL_TAR}" ]; then
  echo "Expected tar not found: ${LOCAL_TAR}" >&2
  exit 1
fi

echo "Preparing remote directories on ${SSH_USER}@${SSH_HOST}:${SSH_PORT}..."
ssh -p "${SSH_PORT}" "${SSH_USER}@${SSH_HOST}" \
  "mkdir -p '${REMOTE_DIR}' '${REMOTE_TAR_DIR}' '${REMOTE_DATA_DIR}'"

echo "Uploading tar + deploy script + env..."
scp -P "${SSH_PORT}" "${LOCAL_TAR}" "${SSH_USER}@${SSH_HOST}:${REMOTE_TAR}"
scp -P "${SSH_PORT}" "${PROJECT_DIR}/scripts/deploy_from_tar.sh" \
  "${SSH_USER}@${SSH_HOST}:${REMOTE_DEPLOY_SCRIPT}"
scp -P "${SSH_PORT}" "${ENV_FILE_LOCAL}" "${SSH_USER}@${SSH_HOST}:${REMOTE_ENV_FILE}"

echo "Running remote deployment..."
ssh -p "${SSH_PORT}" "${SSH_USER}@${SSH_HOST}" "bash -s" <<EOF
set -euo pipefail
chmod +x '${REMOTE_DEPLOY_SCRIPT}'
'${REMOTE_DEPLOY_SCRIPT}' '${REMOTE_TAR}' '${REMOTE_ENV_FILE}' '${CONTAINER_NAME}' '${REMOTE_DATA_DIR}'
EOF

echo
echo "All done."
echo "Server: ${SSH_USER}@${SSH_HOST}"
echo "Container: ${CONTAINER_NAME}"
echo "Logs command:"
echo "  ssh -p ${SSH_PORT} ${SSH_USER}@${SSH_HOST} 'docker logs -f ${CONTAINER_NAME}'"
