# NFS storage

This directory defines the platform's default Kubernetes StorageClass.

## Backend

- Server: `10.0.6.4`
- Export: `/var/nfs/shared/k8s_sc8`
- Provisioner: `nfs.csi.k8s.io`
- StorageClass: `nfs-csi`
- Reclaim policy: `Retain`

Each dynamically provisioned volume uses a directory containing the
namespace, PVC name and PV name.

The Velero StorageClass mapping converts volumes from the previous block
StorageClass to `nfs-csi` during disaster recovery.
