#!/usr/bin/env bash
set -euo pipefail

: "${KUBERNETES_VERSION:?KUBERNETES_VERSION must be set}"

OUT_DIR="${RUNNER_TEMP:-/tmp}/hacwa-helm-rendered"

rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}"

count=0

while IFS= read -r -d '' chart_file; do
  chart_dir="$(dirname "${chart_file}")"
  relative="${chart_dir#./}"
  output_name="${relative//\//__}.yaml"

  echo "===== helm lint ${relative} ====="
  helm lint "${chart_dir}"

  echo "===== helm template ${relative} ====="
  helm template \
    ci \
    "${chart_dir}" \
    --namespace default \
    > "${OUT_DIR}/${output_name}"

  count=$((count + 1))
done < <(
  find platform \
    -type f \
    -name 'Chart.yaml' \
    -print0 |
    sort -z
)

if [[ "${count}" -eq 0 ]]; then
  echo "No local Helm charts found under platform/" >&2
  exit 1
fi

echo
printf 'Rendered %d Helm charts.\n' "${count}"

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
