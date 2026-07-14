# Velero restore requests

This directory provides Git-reviewed, manually triggered Velero restores.

The `velero-restores` Argo CD application deliberately has no automated sync
policy. A commit can prepare a Restore object, but it cannot execute the
restore until the application is manually synced in Argo CD.

## Important behaviour

A Velero Restore begins immediately when its Kubernetes Restore object is
created.

Never enable automated synchronization for the `velero-restores` application.

## Preparing a restore

1. List the available backups:

       kubectl -n velero get backups \
         -o custom-columns=NAME:.metadata.name,PHASE:.status.phase,CREATED:.metadata.creationTimestamp,EXPIRES:.status.expiration

2. Select the appropriate example under `examples/`.

3. Copy it into `requests/` using a unique filename.

4. Replace every `CHANGE-ME` value.

5. Add the new file to `requests/kustomization.yaml`.

6. Commit and push.

7. Review the `velero-restores` diff in Argo CD.

8. Manually sync only the `velero-restores` application.

9. Monitor the Restore and DataDownload objects.

## Example request

Copy an example:

    cp \
      platform/velero-restores/examples/investigation-restore.yaml \
      platform/velero-restores/requests/librenms-investigation-20260714.yaml

Then edit:

    platform/velero-restores/requests/librenms-investigation-20260714.yaml

Add it to:

    platform/velero-restores/requests/kustomization.yaml

For example:

    resources:
      - librenms-investigation-20260714.yaml

## Selecting a backup

Prefer an exact backup for controlled recovery:

    backupName: daily-everything-20260714110000

Velero can also select the most recent successful backup from a schedule:

    scheduleName: daily-everything

Do not specify both `backupName` and `scheduleName`.

## Existing objects

The examples use:

    existingResourcePolicy: none

This is Velero's non-destructive restore policy. Existing objects are skipped
rather than overwritten.

Do not use `existingResourcePolicy: update` without reviewing the effects on
GitOps-managed resources and persistent data.

## Investigation restores

For investigation, restore an application into another namespace:

    namespaceMapping:
      librenms: librenms-investigation

This avoids modifying the production namespace.

## Removing a completed request

After the restore has completed and been verified:

1. Remove its filename from `requests/kustomization.yaml`.
2. Delete the request file from Git.
3. Commit and push.
4. Manually sync `velero-restores` with pruning enabled only when you intend to
   remove the completed Restore object from Kubernetes.

Removing a Restore object does not delete the backup from MinIO.
