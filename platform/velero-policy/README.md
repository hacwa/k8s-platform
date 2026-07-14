# Velero backup policy

This local Helm chart manages recurring Velero backup schedules and their
Prometheus alert rules.

## Routine backup configuration

Edit `values.yaml` for normal policy changes.

### Change the daily time

Change:

    cron: "0 11 * * *"

The chart prepends:

    CRON_TZ=Europe/London

### Change retention

Change:

    retention: "720h0m0s"

Examples:

- 14 days: `336h0m0s`
- 30 days: `720h0m0s`
- 90 days: `2160h0m0s`

### Pause backups

Set:

    paused: true

### Change upload concurrency

Change:

    uploader:
      parallelFilesUpload: 4

Higher values can shorten backups but increase Ceph, CPU, network and MinIO
load.

### Exclude a namespace

Add it under:

    excludedNamespaces:
      - velero

## Alert configuration

Alerts are configured under `alerts` in `values.yaml`.

The default alert policy detects:

- Velero server scrape failure;
- node-agent scrape failure;
- unavailable MinIO BackupStorageLocation;
- no successful daily backup within 27 hours;
- failed, partially failed or invalid backups;
- backup warnings;
- CSI snapshot failures;
- failed data uploads;
- failed data downloads;
- failed or partially failed restores;
- restore validation failures;
- Kopia repository-maintenance failures.

The stale-backup threshold is intentionally longer than 24 hours to allow the
scheduled backup time and normal backup duration before alerting.

## Backup scope

The default policy backs up:

- all Kubernetes namespaces except `velero`;
- cluster-scoped Kubernetes resources;
- supported CSI PVC contents through snapshot data movement into MinIO.

The policy excludes short-lived events, leases and generated CiliumEndpoint
objects.

Container stdout and stderr logs are not Kubernetes API resources and are not
captured by Velero.
