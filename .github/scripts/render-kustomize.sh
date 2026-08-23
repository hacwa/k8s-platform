#!/usr/bin/env bash
set -euo pipefail

: "${KUBERNETES_VERSION:?KUBERNETES_VERSION must be set}"

OUT_DIR="${RUNNER_TEMP:-/tmp}/hacwa-kustomize-rendered"

rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}"

count=0

while IFS= read -r -d '' kustomization; do
  directory="$(dirname "${kustomization}")"
  relative="${directory#./}"
  output_name="${relative//\//__}.yaml"

  echo "===== kustomize build ${relative} ====="

  kustomize build "${directory}" \
    > "${OUT_DIR}/${output_name}"

  count=$((count + 1))
done < <(
  find platform -type f \
    \( \
      -name 'kustomization.yaml' \
      -o -name 'kustomization.yml' \
      -o -name 'Kustomization' \
    \) \
    -print0 |
    sort -z
)

if [[ "${count}" -eq 0 ]]; then
  echo "No Kustomizations found under platform/" >&2
  exit 1
fi

echo
printf 'Rendered %d Kustomizations.\n' "${count}"

mapfile -d '' manifests < <(
  find "${OUT_DIR}" \
    -type f \
    -name '*.yaml' \
    -print0 |
    sort -z
)

kubeconform \
  -summary \
  -kubernetes-version "${KUBERNETES_VERSION}" \
  -schema-location default \
  -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' \
  -ignore-missing-schemas \
  "${manifests[@]}"
