# Haists Website Deployment Checklist

Generated: 2026-03-02

## Pre-Deployment Manual Steps

### 1. Vault Secrets
- [ ] Create `secret/keycloak/haists-website` with key `client_secret` (from Keycloak client setup)
- [ ] Create `secret/haists-website` with key `contact_recipient_email` (recipient email address)
- [ ] Verify both secrets readable by `claude-automation` policy (or whichever policy ESO uses)

### 2. Keycloak Client
- [ ] Create OIDC client `haists-website` in `sentinel` realm
- [ ] Client type: confidential, service account enabled (client_credentials grant)
- [ ] Add audience mapper: include `haists-website` in `aud` claim
- [ ] Valid redirect URIs: `https://www.208.haist.farm/*`, `https://www.haist.farm/*`
- [ ] Store client_secret in Vault `secret/keycloak/haists-website`

### 3. Overwatch Console Auth
- [ ] Verify Overwatch Console accepts tokens from `haists-website` client
- [ ] The website uses client_credentials grant to call `/api/health` on console-sec.208.haist.farm

### 4. Matrix Bot /contact Endpoint
- [ ] Verify grafana-alert-receiver on iac-control (:9095) has `/contact` endpoint deployed
- [ ] Test endpoint: `curl -X POST http://10.0.0.1:9095/contact -H 'Content-Type: application/json' -d '{"name":"test","email":"test@test.com","message":"test"}'`

### 5. Harbor Image
- [ ] Build Docker image: `docker build -t harbor.208.haist.farm/sentinel/haists-website:latest .`
- [ ] Push to Harbor: `docker push harbor.208.haist.farm/sentinel/haists-website:latest`
- [ ] **CRITICAL**: Cosign sign the image (Kyverno blocks unsigned images):
  ```bash
  cosign sign --key /etc/cosign/cosign.key --tlog-upload=false --yes harbor.208.haist.farm/sentinel/haists-website:latest
  ```
- [ ] Alternatively: push code to GitLab and let supply-chain-pipeline.yml CI build + sign automatically

### 6. GitLab Repository
- [ ] Create GitLab project for haists-website (admin1 namespace)
- [ ] Push application code (backend/, frontend/, Dockerfile, .gitlab-ci.yml, catalog-info.yaml)
- [ ] Verify CI pipeline runs (supply-chain-pipeline.yml: build, sign, verify)

## Deployment Steps

### Step 1: Push OKD Manifests (overwatch-gitops)
- [ ] Ensure all files are in `overwatch-gitops/apps/haists-website/`:
  - `deployment.yaml` (Deployment + Service)
  - `external-secret.yaml`
  - `network-policies.yaml`
  - `rbac.yaml` (ServiceAccount + SCC)
  - `service-entries.yaml`
- [ ] Ensure mesh-config files are in place:
  - `apps/mesh-config/virtual-services/haists-website.yaml`
  - `apps/mesh-config/authorization-policies/haists-website-authz.yaml`
- [ ] Ensure ArgoCD app manifest: `clusters/overwatch/apps/haists-website-app.yaml`
- [ ] Commit and push to `main` branch (triggers ArgoCD auto-sync)

### Step 2: Verify ArgoCD Sync
- [ ] Check ArgoCD app `haists-website` appears in openshift-gitops namespace
- [ ] Verify sync status is Synced/Healthy (may take 1-3 minutes)
- [ ] Verify `mesh-config` app re-syncs with new VirtualService + AuthorizationPolicy

### Step 3: Deploy Traefik Routes (pangolin-proxy)
- [ ] Apply updated `sentinel-okd-services.yml` with `router-www-208` entry
- [ ] Apply updated `sentinel-external-services.yml` with `router-www-ext` entry
- [ ] Reload Traefik (file provider auto-reloads, or restart container)

### Step 4: Cloudflare DNS + Tunnel
- [ ] Add DNS CNAME: `www.haist.farm` -> Cloudflare Tunnel
- [ ] Add tunnel ingress rule for `www.haist.farm` -> `https://192.168.12.168:443`
- [ ] **Do NOT** create CNAME for `www.208.haist.farm` (internal only, Tailscale split DNS)

## Post-Deployment Verification

### Health Checks
- [ ] Internal: `curl -k https://www.208.haist.farm/api/health` -> `{"status": "healthy"}`
- [ ] External: `curl https://www.haist.farm/api/health` -> `{"status": "healthy"}`
- [ ] Metrics: `curl -k https://www.208.haist.farm/api/metrics` -> JSON with infrastructure/security data
- [ ] Contact form: POST to `/api/contact` with test payload -> verify Matrix notification

### ArgoCD Status
- [ ] `oc get application haists-website -n openshift-gitops` -> Synced, Healthy
- [ ] `oc get application mesh-config -n openshift-gitops` -> Synced, Healthy
- [ ] No OutOfSync on any related apps

### Pod Health
- [ ] `oc get pods -n haists-website` -> 1/1 Running (+ istio-proxy sidecar = 2/2)
- [ ] `oc logs -n haists-website -l app.kubernetes.io/name=haists-website -c haists-website` -> startup log, no errors
- [ ] `oc get externalsecret -n haists-website` -> SecretSynced

### Kyverno Compliance
- [ ] `oc get policyreport -n haists-website` -> all PASS, no FAIL
- [ ] Verify image signature validation passed (check Kyverno admission logs if issues)

### Istio Mesh
- [ ] `oc get virtualservice -n haists-website` -> haists-website listed
- [ ] `oc get authorizationpolicy -n haists-website` -> deny-all + allow-ingress-gateway
- [ ] `oc get serviceentry -n haists-website` -> pangolin-services + matrix-bot
- [ ] Verify sidecar injection: pod should show 2/2 containers

### Network Policies
- [ ] `oc get networkpolicy -n haists-website` -> 3 policies listed
- [ ] Test that external egress is blocked except allowed destinations

## Rollback Procedure

### Quick Rollback (ArgoCD)
1. Scale deployment to 0: modify `deployment.yaml` replicas to 0, push to main
2. ArgoCD auto-syncs and scales down pods
3. Traefik still has route but returns 502 (no backends)

### Full Rollback
1. Remove ArgoCD app: delete `clusters/overwatch/apps/haists-website-app.yaml`, push to main
2. ArgoCD prune deletes all resources in haists-website namespace
3. Remove Traefik routes from `sentinel-okd-services.yml` and `sentinel-external-services.yml`
4. Remove Cloudflare DNS CNAME and tunnel ingress rule
5. Remove mesh-config files:
   - `apps/mesh-config/virtual-services/haists-website.yaml`
   - `apps/mesh-config/authorization-policies/haists-website-authz.yaml`

### Emergency (Direct, bypasses GitOps)
Only if ArgoCD is down:
```bash
oc delete deployment haists-website -n haists-website
oc delete service haists-website -n haists-website
```
Note: ArgoCD will recreate these on next sync cycle.

## Architecture Notes

- **Routing**: Traefik -> HAProxy:8081 -> Istio IngressGateway:31080 -> mTLS -> haists-website:8080
- **External**: Cloudflare Tunnel -> cloudflared -> Traefik:443 -> same path above
- **Auth**: OIDC client_credentials flow to Keycloak for Console API token
- **Contact**: HTTP POST to Matrix bot on iac-control:9095 (no TLS, internal only)
- **Secrets**: ExternalSecrets from Vault (OIDC client_secret, contact email)
- **Security**: Zero-trust (deny-all NetworkPolicy + AuthorizationPolicy), non-root, SCC-locked UID 1001
