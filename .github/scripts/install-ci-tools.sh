#!/usr/bin/env bash
set -euo pipefail

BIN_DIR="${RUNNER_TEMP:-/tmp}/hacwa-ci-bin"
mkdir -p "${BIN_DIR}"

if [[ -n "${GITHUB_PATH:-}" ]]; then
  printf '%s\n' "${BIN_DIR}" >> "${GITHUB_PATH}"
fi

case "$(uname -m)" in
  x86_64)
    ARCH='amd64'
    GITLEAKS_ARCH='x64'
    ;;
  aarch64|arm64)
    ARCH='arm64'
    GITLEAKS_ARCH='arm64'
    ;;
  *)
    echo "Unsupported architecture: $(uname -m)" >&2
    exit 1
    ;;
esac

install_archive_binary() {
  local url="$1"
  local binary="$2"
  local tmp
  local found

  tmp="$(mktemp -d)"

  curl \
    --fail \
    --silent \
    --show-error \
    --location \
    "${url}" \
    -o "${tmp}/archive.tar.gz"

  tar -xzf "${tmp}/archive.tar.gz" -C "${tmp}"

  found="$(
    find "${tmp}" -type f -name "${binary}" -print -quit
  )"

  if [[ -z "${found}" ]]; then
    echo "Could not find ${binary} in ${url}" >&2
    rm -rf "${tmp}"
    exit 1
  fi

  install -m 0755 "${found}" "${BIN_DIR}/${binary}"
  rm -rf "${tmp}"
}

for tool in "$@"; do
  case "${tool}" in
    kustomize)
      : "${KUSTOMIZE_VERSION:?KUSTOMIZE_VERSION must be set}"

      install_archive_binary \
        "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${KUSTOMIZE_VERSION}/kustomize_v${KUSTOMIZE_VERSION}_linux_${ARCH}.tar.gz" \
        kustomize
      ;;

    kubeconform)
      : "${KUBECONFORM_VERSION:?KUBECONFORM_VERSION must be set}"

      install_archive_binary \
        "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-linux-${ARCH}.tar.gz" \
        kubeconform
      ;;

    actionlint)
      : "${ACTIONLINT_VERSION:?ACTIONLINT_VERSION must be set}"

      install_archive_binary \
        "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_${ARCH}.tar.gz" \
        actionlint
      ;;

    gitleaks)
      : "${GITLEAKS_VERSION:?GITLEAKS_VERSION must be set}"

      install_archive_binary \
        "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${GITLEAKS_ARCH}.tar.gz" \
        gitleaks
      ;;

    *)
      echo "Unknown CI tool: ${tool}" >&2
      exit 1
      ;;
  esac
done
