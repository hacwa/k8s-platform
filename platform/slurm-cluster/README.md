# HACWA Slurm on Kubernetes

Argo CD reads this stack from the public `hacwa/k8s-platform` GitHub repository,
branch `main`. Keycloak provisioning and the infrastructure rebuild pipeline
remain in their existing private GitLab repositories.

## GitOps deployment order

| Wave | Application | Source | Purpose |
| --- | --- | --- | --- |
| 68 | slurm-smb-csi | platform/slurm-smb-csi | Linux SMB CSI driver, worker nodes only |
| 69 | slurm-operator | platform/slurm-operator | Slinky operator, CRDs and webhook |
| 70 | slurm-bootstrap | platform/slurm-bootstrap | Namespace, external secrets, retained storage, database and network policy |
| 71 | slurm-cluster | platform/slurm-cluster | Controller, accounting, REST API, one CPU worker and accounting/smoke-test hook |
| 72 | slurm-web | platform/slurm-web | Slurm-web agent, OIDC gateway and HTTPS route |

The existing ApplicationSet discovers these catalogue files. Applications use
self-heal, server-side apply and no automatic pruning. The operator uses an
internal self-signed webhook certificate through the existing cert-manager;
it does not request a public certificate.

Pinned dependencies: Slinky charts 1.2.3, Slurm 26.05 on Ubuntu 26.04,
SMB CSI 1.20.3, Slurm-web 7.0.0 and MariaDB 11.8.6. Application container images
are pinned by digest. Commit chart lock files; dependency archives are rebuilt
by Helm and excluded from Git.

## Required AWS secret properties

Manually add these properties to the existing JSON secret `hacwa_aws_secrets`
in `eu-west-2`, preserving every other existing property. Do not create a second
AWS secret. External Secrets uses the existing `aws-secrets-manager` store.
Do not paste secret values into Git, PRs, job logs or chat.

| JSON property | Value |
| --- | --- |
| slurm-auth-key | A new independent value from `openssl rand -hex 512` |
| slurm-jwt-key | A new independent value from `openssl rand -hex 32` |
| slurm-db-root-password | A new independent value from `openssl rand -hex 32` |
| slurm-db-password | A new independent value from `openssl rand -hex 32` |
| slurm-web-jwt-key | A new independent value from `openssl rand -hex 32` |
| slurm-web-session-key | A new independent value from `openssl rand -hex 64` |
| slurm-web-client-secret | The exact existing Keycloak `slurm-web` client secret, also used by `TF_VAR_slurm_web_client_secret` in the private Keycloak project |
| slurm-smb-username | The existing SMB account (`Administrator` for the pilot) |
| slurm-smb-password | That account's existing Windows SMB password |

Generate each value independently on a trusted local terminal and enter it in
AWS Secrets Manager. ESO writes the literal strings, without base64 decoding.
Reuse any values already provisioned for this stack. Rotating database passwords
requires a coordinated SQL password change; changing AWS alone does not alter
an initialized MariaDB account. Coordinate Slurm authentication-key changes and
restart the web deployments after changing their signing, session or OIDC keys.

## Workload and access

The `media` partition starts with one worker requesting and limiting one CPU
and 2 GiB memory. The initial two-CPU request could not be scheduled on either
eligible worker; this pilot size reserves its full CPU allocation. All components select Linux worker nodes, with no GPU-taint
toleration. Dashboard images additionally require amd64. Confirm current worker
capacity in the cluster; repository configuration does not establish live capacity.

The SMB share `//10.0.0.120/TV Shows` is mounted at `/mnt/plex_tv` with read-only
CSI, PVC and container mounts, plus `ro,nosuid,nodev,noexec`. Its static PV's 1 TiB
capacity is a binding value, not a share quota. Workspace output, manifests and
logs use `/srv/slurm-media` on retained NFS storage. The bootstrap hook creates
the `media` accounting association for the service user `slurm`, then requires
a successful batch job checking source readability and workspace writability.

This stage installs the scheduler and dashboard. The pinned upstream worker
image does not include FFmpeg or the pilot's Python conversion scripts. The
existing pilot VM and media are unchanged; transferring conversion jobs requires
a separately built worker image and reviewed job scripts. No automatic media
conversion or replacement is enabled here.

The gateway is `https://slurm.hacwa.co.uk`, using the existing external Gateway
and wildcard certificate. DNS and the external proxy must route that hostname
to the cluster's existing HTTPS ingress. OIDC issuer:
`https://keycloak.hacwa.co.uk/realms/master`; callback:
`https://slurm.hacwa.co.uk/api/oidc/callback`. The Keycloak client is `slurm-web`,
with PKCE S256. Its group mapper supplies unprefixed names. Only `SlurmUsers`
and `SlurmAdmins` can sign in. Users see their own jobs; admins can view all
jobs and accounting. Dashboard access does not create Unix or Slurm accounts.

The agent and Slurm REST API remain internal. Network policy permits ingress
within the Slurm namespace, operator-to-REST traffic from `slurm-system`, and
HTTPS Gateway-to-web-gateway traffic on port 5011. Egress is unrestricted for
DNS, Keycloak, storage and normal cluster communication.

## Verification

After merging and Argo CD reconciliation, inspect the five Applications in the
existing Argo CD UI. No port forwards or Argo CD CLI are required. From an
existing authorized Kubernetes session:

```sh
kubectl -n slurm get externalsecrets,pvc,pods
kubectl -n slurm get controllers,accountings,restapis,nodesets,tokens
kubectl -n slurm logs job/slurm-accounting-bootstrap
kubectl -n slurm get httproute slurm-web
```

All five ExternalSecrets must be Ready, all PVCs Bound, and the accounting
bootstrap Job Complete. Its log includes the successful batch job ID and
account association. Confirm the HTTPRoute is accepted/resolved, then sign in
at the public URL using the existing Keycloak account in `SlurmAdmins`.
Validate admin views and a separate `SlurmUsers` account's own-job restrictions.
Static render/schema checks cannot establish live image startup, NFS/SMB
reachability, DNS/proxy routing or successful SSO.

Web and database ConfigMaps use Kustomize-generated content hashes so committed
configuration changes update pod templates automatically.

## Backup and recovery

The existing Velero daily policy includes the `slurm` namespace. A MariaDB
pre-backup hook creates an atomic, transaction-consistent logical dump on
`slurm-db-backups`; failure fails the backup hook. Its raw live datadir is
excluded from filesystem backup. On a new empty datadir the MariaDB init script
imports the restored logical dump. A retained existing datadir starts normally
without importing over it.

Controller state and workspace are included in filesystem backup. Source SMB
media is excluded on controller/worker pod templates. Operator runtime namespace
and generated Slurm CRs are excluded from Velero; GitOps reconstructs them.
The PVCs/PV use Retain and Argo deletion/pruning protection.

For a rebuild, retain/restore the required AWS properties, restore persistent
NFS data/PVC bindings using the platform's existing DR process, then allow the
ordered GitOps applications to reconcile. Keep jobs stopped until database and
controller recovery are verified. If restoring into a new datadir, ensure the
logical backup PVC is restored before starting MariaDB. Inspect the restore
log, accounting associations and smoke-test completion before submitting work.
An absent or failed logical dump is not an accounting recovery point. This
configuration requires a successful live backup/restore drill before claiming
Slurm disaster recovery has been proven.
