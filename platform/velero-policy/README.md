# Velero backup policy

This local Helm chart manages recurring Velero backup schedules.

## Routine configuration

Edit `values.yaml` for normal policy changes.

## Change the daily time

Change:

    cron: "0 11 * * *"

The chart prepends:

    CRON_TZ=Europe/London

## Change retention

Change:

    retention: "720h0m0s"

Examples:

- 14 days: `336h0m0s`
- 30 days: `720h0m0s`
- 90 days: `2160h0m0s`

## Pause backups

Set:

    paused: true

## Change upload concurrency

Change:

    uploader:
      parallelFilesUpload: 4

Higher values can shorten backups but increase Ceph, CPU, network and MinIO
load.

## Exclude a namespace

Add it under:

    excludedNamespaces:
      - velero

## Add another schedule

Copy the complete `daily-everything` block beneath `schedules`, give it a
unique name, and change its cron, retention or scope.

## Default scope

The default policy backs up:

- all Kubernetes namespaces except `velero`;
- cluster-scoped Kubernetes resources;
- supported CSI PVC contents through snapshot data movement into MinIO.

The policy excludes short-lived events, leases and generated CiliumEndpoint
objects.

Container stdout and stderr logs are not Kubernetes API resources and are not
captured by Velero.
