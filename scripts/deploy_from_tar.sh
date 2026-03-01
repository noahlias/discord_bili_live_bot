#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy_from_tar.sh <image.tar|image.tar.gz> <env_file> [container_name] [data_dir]

Example:
  ./scripts/deploy_from_tar.sh dist/discord-live-bot_slimcheck_linux_amd64.tar.gz .env
  ./scripts/deploy_from_tar.sh /opt/discord/discord-live-bot_slimcheck_linux_amd64.tar.gz /opt/discord/.env discord-live-bot /opt/discord/data
EOF
}

if [ "${#}" -lt 2 ] || [ "${#}" -gt 4 ]; then
  usage
  exit 1
fi

IMAGE_TAR="${1}"
ENV_FILE="${2}"
CONTAINER_NAME="${3:-discord-live-bot}"
DATA_DIR="${4:-$(pwd)/data}"
DOCKER_DNS="${DOCKER_DNS:-}"
DOCKER_NETWORK_MODE="${DOCKER_NETWORK_MODE:-bridge}"

if [ ! -f "${IMAGE_TAR}" ]; then
  echo "Image tar file not found: ${IMAGE_TAR}" >&2
  exit 1
fi

if [ ! -f "${ENV_FILE}" ]; then
  echo "Env file not found: ${ENV_FILE}" >&2
  exit 1
fi

mkdir -p "${DATA_DIR}"

echo "Loading image from ${IMAGE_TAR}..."
if [[ "${IMAGE_TAR}" == *.tar.gz ]] || [[ "${IMAGE_TAR}" == *.tgz ]]; then
  LOAD_OUTPUT="$(gunzip -c "${IMAGE_TAR}" | docker load)"
else
  LOAD_OUTPUT="$(docker load -i "${IMAGE_TAR}")"
fi
printf '%s\n' "${LOAD_OUTPUT}"

IMAGE_REF="$(printf '%s\n' "${LOAD_OUTPUT}" | awk -F': ' '/Loaded image:/{print $2}' | tail -n 1)"
if [ -z "${IMAGE_REF}" ]; then
  echo "Could not detect loaded image tag from docker load output." >&2
  echo "Please retag image manually and rerun deployment." >&2
  exit 1
fi

echo "Fixing data directory permissions for container user..."
APP_UID="$(docker run --rm --entrypoint sh "${IMAGE_REF}" -lc 'id -u')"
APP_GID="$(docker run --rm --entrypoint sh "${IMAGE_REF}" -lc 'id -g')"
if chown -R "${APP_UID}:${APP_GID}" "${DATA_DIR}" 2>/dev/null; then
  echo "Data dir ownership set to ${APP_UID}:${APP_GID} (${DATA_DIR})"
else
  echo "Warning: failed to chown ${DATA_DIR}; trying chmod fallback..." >&2
  chmod -R a+rwX "${DATA_DIR}" 2>/dev/null || true
fi

if docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
  echo "Removing existing container ${CONTAINER_NAME}..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null
fi

DOCKER_DNS_ARGS=()
if [ "${DOCKER_NETWORK_MODE}" != "host" ] && [ -n "${DOCKER_DNS}" ]; then
  IFS=',' read -r -a DNS_SERVERS <<< "${DOCKER_DNS}"
  for dns in "${DNS_SERVERS[@]}"; do
    if [ -n "${dns}" ]; then
      DOCKER_DNS_ARGS+=(--dns "${dns}")
    fi
  done
fi
if [ "${DOCKER_NETWORK_MODE}" = "host" ] && [ -n "${DOCKER_DNS}" ]; then
  echo "Warning: DOCKER_DNS ignored because DOCKER_NETWORK_MODE=host uses host resolver." >&2
fi

echo "Starting container ${CONTAINER_NAME}..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  --restart unless-stopped \
  --network "${DOCKER_NETWORK_MODE}" \
  --env-file "${ENV_FILE}" \
  "${DOCKER_DNS_ARGS[@]}" \
  -v "${DATA_DIR}:/app/data" \
  "${IMAGE_REF}" >/dev/null

echo
echo "Deploy complete."
echo "Container: ${CONTAINER_NAME}"
echo "Image: ${IMAGE_REF}"
echo "Network: ${DOCKER_NETWORK_MODE}"
echo "Logs: docker logs -f ${CONTAINER_NAME}"
