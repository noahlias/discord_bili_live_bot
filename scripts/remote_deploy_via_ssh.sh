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

resolve_rclone_destination() {
  local remote_path="$1"
  local configured_remote="${RCLONE_REMOTE:-}"

  if [ -n "${configured_remote}" ]; then
    local normalized_remote="${configured_remote%:}"
    if rclone listremotes | grep -Fxq "${normalized_remote}:"; then
      printf '%s\n' "${normalized_remote}:${remote_path}"
      return
    fi
  fi

  local backend=":sftp,host=${SSH_HOST},user=${SSH_USER},port=${SSH_PORT}"
  if [ -n "${RCLONE_SFTP_KEY_FILE:-}" ]; then
    backend="${backend},key_file=${RCLONE_SFTP_KEY_FILE}"
  fi
  printf '%s:%s\n' "${backend}" "${remote_path}"
}

SSH_PORT="${SSH_PORT:-22}"
IMAGE_NAME="${IMAGE_NAME:-discord-live-bot}"
IMAGE_TAG="${IMAGE_TAG:-slimcheck}"
TAR_OUT_DIR="${TAR_OUT_DIR:-dist}"
ENV_FILE_LOCAL="${ENV_FILE_LOCAL:-.env}"
UPLOAD_METHOD="${UPLOAD_METHOD:-rsync}"
RCLONE_REMOTE="${RCLONE_REMOTE:-}"
REMOTE_DIR="${REMOTE_DIR:-/opt/discord-live-bot}"
REMOTE_ENV_FILE="${REMOTE_ENV_FILE:-${REMOTE_DIR}/.env}"
REMOTE_TAR_DIR="${REMOTE_TAR_DIR:-${REMOTE_DIR}/dist}"
REMOTE_DATA_DIR="${REMOTE_DATA_DIR:-${REMOTE_DIR}/data}"
CONTAINER_NAME="${CONTAINER_NAME:-discord-live-bot}"
DOCKER_DNS="${DOCKER_DNS:-}"
DOCKER_NETWORK_MODE="${DOCKER_NETWORK_MODE:-host}"

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

echo "Uploading tar + deploy script + env (method: ${UPLOAD_METHOD})..."
if [ "${UPLOAD_METHOD}" = "rsync" ]; then
  if ! command -v rsync >/dev/null 2>&1; then
    echo "rsync is not installed locally." >&2
    exit 1
  fi
  if ! ssh -p "${SSH_PORT}" "${SSH_USER}@${SSH_HOST}" "command -v rsync >/dev/null 2>&1"; then
    echo "Remote rsync not found; falling back to scp." >&2
    scp -P "${SSH_PORT}" "${LOCAL_TAR}" "${SSH_USER}@${SSH_HOST}:${REMOTE_TAR}"
    scp -P "${SSH_PORT}" "${PROJECT_DIR}/scripts/deploy_from_tar.sh" \
      "${SSH_USER}@${SSH_HOST}:${REMOTE_DEPLOY_SCRIPT}"
    scp -P "${SSH_PORT}" "${ENV_FILE_LOCAL}" "${SSH_USER}@${SSH_HOST}:${REMOTE_ENV_FILE}"
  else
    RSYNC_SSH="ssh -p ${SSH_PORT}"
    rsync -azP --append-verify -e "${RSYNC_SSH}" "${LOCAL_TAR}" "${SSH_USER}@${SSH_HOST}:${REMOTE_TAR}"
    rsync -azP -e "${RSYNC_SSH}" "${PROJECT_DIR}/scripts/deploy_from_tar.sh" "${SSH_USER}@${SSH_HOST}:${REMOTE_DEPLOY_SCRIPT}"
    rsync -azP -e "${RSYNC_SSH}" "${ENV_FILE_LOCAL}" "${SSH_USER}@${SSH_HOST}:${REMOTE_ENV_FILE}"
  fi
elif [ "${UPLOAD_METHOD}" = "scp" ]; then
  scp -P "${SSH_PORT}" "${LOCAL_TAR}" "${SSH_USER}@${SSH_HOST}:${REMOTE_TAR}"
  scp -P "${SSH_PORT}" "${PROJECT_DIR}/scripts/deploy_from_tar.sh" \
    "${SSH_USER}@${SSH_HOST}:${REMOTE_DEPLOY_SCRIPT}"
  scp -P "${SSH_PORT}" "${ENV_FILE_LOCAL}" "${SSH_USER}@${SSH_HOST}:${REMOTE_ENV_FILE}"
elif [ "${UPLOAD_METHOD}" = "rclone" ]; then
  if ! command -v rclone >/dev/null 2>&1; then
    echo "rclone is not installed locally." >&2
    exit 1
  fi
  TAR_DEST="$(resolve_rclone_destination "${REMOTE_TAR}")"
  SCRIPT_DEST="$(resolve_rclone_destination "${REMOTE_DEPLOY_SCRIPT}")"
  ENV_DEST="$(resolve_rclone_destination "${REMOTE_ENV_FILE}")"
  rclone copyto "${LOCAL_TAR}" "${TAR_DEST}"
  rclone copyto "${PROJECT_DIR}/scripts/deploy_from_tar.sh" "${SCRIPT_DEST}"
  rclone copyto "${ENV_FILE_LOCAL}" "${ENV_DEST}"
else
  echo "Unsupported UPLOAD_METHOD: ${UPLOAD_METHOD} (use: rsync, scp or rclone)" >&2
  exit 1
fi

echo "Running remote deployment..."
ssh -p "${SSH_PORT}" "${SSH_USER}@${SSH_HOST}" "bash -s" <<EOF
set -euo pipefail
chmod +x '${REMOTE_DEPLOY_SCRIPT}'
DOCKER_DNS='${DOCKER_DNS}' DOCKER_NETWORK_MODE='${DOCKER_NETWORK_MODE}' '${REMOTE_DEPLOY_SCRIPT}' '${REMOTE_TAR}' '${REMOTE_ENV_FILE}' '${CONTAINER_NAME}' '${REMOTE_DATA_DIR}'
EOF

echo
echo "All done."
echo "Server: ${SSH_USER}@${SSH_HOST}"
echo "Container: ${CONTAINER_NAME}"
echo "Network: ${DOCKER_NETWORK_MODE}"
echo "Logs command:"
echo "  ssh -p ${SSH_PORT} ${SSH_USER}@${SSH_HOST} 'docker logs -f ${CONTAINER_NAME}'"
