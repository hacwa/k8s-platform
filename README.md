# k8s-platform

Public GitOps repository for the Kubernetes platform layer.

This repo contains non-secret Kubernetes platform configuration for:

- Argo CD app-of-apps
- MetalLB
- Envoy Gateway
- cert-manager
- Let's Encrypt DNS-01 via Cloudflare
- wildcard certificate for `*.hacwa.co.uk`
- Argo CD SSO/RBAC/external route
- NVIDIA device plugin

## Secrets

This repository must not contain secrets.

The following are created by the private bootstrap pipeline instead:

- Cloudflare API token secret
- Kubernetes admin kubeconfig
- SSH keys
- Proxmox API tokens
- ETCD CA private key
- Kubernetes CA private keys

## Required private bootstrap secret

Before syncing the cert-manager configuration, the private bootstrap pipeline must create:

Namespace:

```text
cert-manager

Secret:

cloudflare-api-token-secret

Key:

api-token

