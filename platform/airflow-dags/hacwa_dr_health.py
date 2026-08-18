import json
import ssl
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pendulum
from airflow.sdk import dag, task


KUBERNETES_API = "https://kubernetes.default.svc"
SERVICE_ACCOUNT_TOKEN = "/var/run/secrets/kubernetes.io/serviceaccount/token"
SERVICE_ACCOUNT_CA = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
MAX_SUCCESSFUL_BACKUP_AGE_HOURS = 27


def kubernetes_get(path):
    with open(SERVICE_ACCOUNT_TOKEN, "r", encoding="utf-8") as token_file:
        token = token_file.read().strip()

    context = ssl.create_default_context(cafile=SERVICE_ACCOUNT_CA)
    request = Request(
        f"{KUBERNETES_API}{path}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )

    try:
        with urlopen(request, context=context, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Kubernetes API request {path} returned HTTP {exc.code}: {body[:500]}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Kubernetes API request {path} failed: {exc}") from exc


def parse_kubernetes_timestamp(value):
    if not value:
        return None

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dag(
    dag_id="hacwa_dr_health",
    description="Read-only health audit for Kubernetes, Argo CD and Velero DR state.",
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 18, tz="Europe/London"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(seconds=30),
    },
    tags=["hacwa", "kubernetes", "dr", "health"],
)
def hacwa_dr_health():
    @task
    def check_kubernetes_api():
        version = kubernetes_get("/version")

        result = {
            "healthy": True,
            "gitVersion": version.get("gitVersion", "unknown"),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result

    @task
    def check_nodes(api_status):
        del api_status

        response = kubernetes_get("/api/v1/nodes")
        not_ready = []

        for node in response.get("items", []):
            name = node.get("metadata", {}).get("name", "unknown")
            conditions = node.get("status", {}).get("conditions", [])
            ready = next(
                (
                    condition
                    for condition in conditions
                    if condition.get("type") == "Ready"
                ),
                None,
            )

            if not ready or ready.get("status") != "True":
                not_ready.append(name)

        result = {
            "healthy": not not_ready,
            "total": len(response.get("items", [])),
            "notReady": sorted(not_ready),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result

    @task
    def check_namespaces(api_status):
        del api_status

        response = kubernetes_get("/api/v1/namespaces")
        terminating = []

        for namespace in response.get("items", []):
            if namespace.get("status", {}).get("phase") == "Terminating":
                terminating.append(
                    namespace.get("metadata", {}).get("name", "unknown")
                )

        result = {
            "healthy": not terminating,
            "total": len(response.get("items", [])),
            "terminating": sorted(terminating),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result

    @task
    def check_pvcs(api_status):
        del api_status

        response = kubernetes_get("/api/v1/persistentvolumeclaims")
        unhealthy = []

        for pvc in response.get("items", []):
            phase = pvc.get("status", {}).get("phase", "Unknown")
            if phase != "Bound":
                metadata = pvc.get("metadata", {})
                unhealthy.append(
                    {
                        "namespace": metadata.get("namespace", "unknown"),
                        "name": metadata.get("name", "unknown"),
                        "phase": phase,
                    }
                )

        result = {
            "healthy": not unhealthy,
            "total": len(response.get("items", [])),
            "unhealthy": unhealthy,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result

    @task
    def check_argocd(api_status):
        del api_status

        response = kubernetes_get(
            "/apis/argoproj.io/v1alpha1/namespaces/argocd/applications"
        )
        unhealthy = []

        for application in response.get("items", []):
            metadata = application.get("metadata", {})
            status = application.get("status", {})
            sync_status = status.get("sync", {}).get("status", "Unknown")
            health_status = status.get("health", {}).get("status", "Unknown")

            if sync_status != "Synced" or health_status != "Healthy":
                unhealthy.append(
                    {
                        "name": metadata.get("name", "unknown"),
                        "sync": sync_status,
                        "health": health_status,
                    }
                )

        result = {
            "healthy": not unhealthy,
            "total": len(response.get("items", [])),
            "unhealthy": unhealthy,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result

    @task
    def check_velero(api_status):
        del api_status

        locations = kubernetes_get(
            "/apis/velero.io/v1/namespaces/velero/backupstoragelocations"
        )
        unavailable_locations = []

        for location in locations.get("items", []):
            phase = location.get("status", {}).get("phase", "Unknown")
            if phase != "Available":
                unavailable_locations.append(
                    {
                        "name": location.get("metadata", {}).get(
                            "name", "unknown"
                        ),
                        "phase": phase,
                    }
                )

        backups = kubernetes_get(
            "/apis/velero.io/v1/namespaces/velero/backups"
        ).get("items", [])

        completed = []

        for backup in backups:
            status = backup.get("status", {})
            errors = int(status.get("errors", 0) or 0)

            if status.get("phase") == "Completed" and errors == 0:
                completed.append(backup)

        completed.sort(
            key=lambda item: item.get("status", {}).get("completionTimestamp")
            or item.get("metadata", {}).get("creationTimestamp", ""),
            reverse=True,
        )

        latest = completed[0] if completed else None
        latest_name = None
        latest_completion = None
        latest_age_hours = None
        latest_warnings = None

        if latest:
            latest_name = latest.get("metadata", {}).get("name", "unknown")
            latest_status = latest.get("status", {})
            latest_completion = latest_status.get("completionTimestamp")
            latest_warnings = int(latest_status.get("warnings", 0) or 0)

            timestamp = parse_kubernetes_timestamp(
                latest_completion
                or latest.get("metadata", {}).get("creationTimestamp")
            )

            if timestamp:
                latest_age_hours = round(
                    (
                        datetime.now(timezone.utc)
                        - timestamp.astimezone(timezone.utc)
                    ).total_seconds()
                    / 3600,
                    2,
                )

        backup_is_fresh = (
            latest_age_hours is not None
            and latest_age_hours <= MAX_SUCCESSFUL_BACKUP_AGE_HOURS
        )

        result = {
            "healthy": (
                not unavailable_locations
                and latest is not None
                and backup_is_fresh
            ),
            "backupStorageLocations": len(locations.get("items", [])),
            "unavailableBackupStorageLocations": unavailable_locations,
            "latestSuccessfulBackup": latest_name,
            "latestSuccessfulBackupCompleted": latest_completion,
            "latestSuccessfulBackupAgeHours": latest_age_hours,
            "latestSuccessfulBackupWarnings": latest_warnings,
            "maximumSuccessfulBackupAgeHours": MAX_SUCCESSFUL_BACKUP_AGE_HOURS,
        }

        print(json.dumps(result, indent=2, sort_keys=True))
        return result

    @task
    def build_summary(api, nodes, namespaces, pvcs, argocd, velero):
        checks = {
            "kubernetesApi": api,
            "nodes": nodes,
            "namespaces": namespaces,
            "pvcs": pvcs,
            "argocd": argocd,
            "velero": velero,
        }

        failures = [
            name
            for name, result in checks.items()
            if not result.get("healthy", False)
        ]

        summary = {
            "healthy": not failures,
            "failedChecks": failures,
            "checks": checks,
        }

        print("===== HACWA DR HEALTH SUMMARY =====")
        print(json.dumps(summary, indent=2, sort_keys=True))

        if failures:
            raise RuntimeError(
                "HACWA DR health audit failed: " + ", ".join(failures)
            )

        return summary

    api = check_kubernetes_api()
    nodes = check_nodes(api)
    namespaces = check_namespaces(api)
    pvcs = check_pvcs(api)
    argocd = check_argocd(api)
    velero = check_velero(api)

    build_summary(
        api=api,
        nodes=nodes,
        namespaces=namespaces,
        pvcs=pvcs,
        argocd=argocd,
        velero=velero,
    )


hacwa_dr_health()
