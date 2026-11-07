---
sidebar_position: 7
title: "Kubernetes"
description: "Running tuos on Kubernetes with its Helm chart: one gateway pod with a data volume, settings and secrets from Helm values, and memory in GCS or MinIO"
---

# Running on Kubernetes

The Helm chart in [`deploy/helm/tuos`](https://github.com/sreent/hermes/tree/main/deploy/helm/tuos) runs tuos in one pod, from the same image as [Docker](./docker.md). The pod runs the messaging gateway, which also runs scheduled jobs, and the web dashboard. tuos is built on Nous Research's Hermes Agent, whose settings and environment variables keep Hermes's names (`~/.hermes`, `HERMES_*`).

| Object | Purpose |
|---|---|
| StatefulSet with one pod | Runs `tuos gateway run`, supervised inside the container |
| PersistentVolumeClaim `data-<release>-0` | `/opt/data`: `config.yaml`, `.env`, sessions, skills, cron jobs, logs |
| ConfigMap | The `config` value, pinned over `/opt/data/config.yaml` |
| Secret | The `secrets.env` value, as the pod's environment (or name your own Secret) |
| ServiceAccount | The pod's identity, for example for GKE Workload Identity |
| Service `<release>-dashboard` | Only with `dashboard.expose`: the dashboard on the network |

There is only ever one pod: a chat platform's bot token takes one connection at a time, and the sessions database on the volume takes one writer. The StatefulSet stops the old pod before it starts a new one.

## The image

The chart runs the image this repository publishes on GitHub's container registry, `ghcr.io/sreent/tuos`, for amd64 and arm64:

| Tag | What it is |
|---|---|
| `main` (the chart's default), `latest` | The newest commit on the main branch |
| `vX.Y.Z` | A release |
| `main-desktop`, `latest-desktop`, `vX.Y.Z-desktop` | The same, with the packages the [bots' screens](./features/bot-screen.md) need |

Set `image.tag` to a release tag to pin one; with a pinned tag, `image.pullPolicy: IfNotPresent` saves the registry check on each restart. To run your own build instead, push it to a registry the cluster can pull from and set `image.repository` and `image.tag`. [Docker → What the Dockerfile does](./docker.md#what-the-dockerfile-does) describes what goes into it.

## Install

Put secrets in a Secret, then install the chart:

```bash
kubectl create namespace tuos
kubectl create secret generic tuos-env -n tuos \
  --from-literal=OPENROUTER_API_KEY=... \
  --from-literal=TELEGRAM_BOT_TOKEN=... \
  --from-literal=TELEGRAM_ALLOWED_USERS=...

helm install tuos deploy/helm/tuos -n tuos \
  --set secrets.existingSecret=tuos-env
```

Any key from [`.env.example`](https://github.com/sreent/hermes/blob/main/.env.example) can go in the Secret, and `kubectl create secret generic tuos-env --from-env-file=.env` turns an existing `.env` into one.

Then choose a model and connect chat platforms from inside the pod, and restart the gateway to apply them:

```bash
kubectl exec -it -n tuos tuos-0 -- tuos setup
kubectl exec -n tuos tuos-0 -- tuos gateway restart
```

What you set up this way is saved on the volume, so it survives restarts and upgrades. `kubectl logs -f -n tuos tuos-0` follows the gateway. To start the pod idle for this first setup, without the gateway, install with `--set-json 'args=["sleep","infinity"]'` and upgrade with the default `args` afterwards.

## Settings from Helm values

`config` holds `config.yaml` settings. The chart mounts them as the [managed scope](./managed-scope.md): they are laid over `/opt/data/config.yaml` key by key, and the dashboard and `tuos config set` show them as managed and cannot change them. Every key the chart does not set stays editable in the pod. Changing `config` restarts the pod.

```yaml
config:
  timezone: Europe/London
  memory:
    storage:
      backend: gcs
      bucket: my-tuos-memory
```

`config` becomes a ConfigMap, which anyone who can read the namespace's ConfigMaps can read, so it is no place for secrets.

## Secrets

The pod's environment comes from `secrets.existingSecret`, a Secret you manage (by hand, with External Secrets, Sealed Secrets and so on), or from `secrets.env`, a map of keys from which the chart creates the Secret (the values are then also stored in the Helm release). A changed Secret applies when the pod restarts: `helm upgrade` restarts it when `secrets.env` changes, and `kubectl rollout restart statefulset/tuos -n tuos` does it for your own Secret.

A key that is also set in `/opt/data/.env` takes its value from that file. `tuos setup` and the dashboard's Keys page write there, so delete a key there to let the Secret's value apply.

## Memory in a bucket

By default `MEMORY.md` and `USER.md` live on the data volume. With [`memory.storage`](./configuration.md#memory-storage) they live in a bucket instead, so memory outlives the volume and can be shared. Objects are stored under `<prefix><profile>/memories/`: agents that use the same bucket and `prefix` share memory, and an agent with its own `prefix` keeps its memory to itself.

### Google Cloud Storage on GKE

With Workload Identity Federation for GKE, the pod signs in as its Kubernetes service account and no key is stored anywhere. Create the bucket, and let the chart's service account (named after the release: `tuos` in namespace `tuos` here) use its objects:

```bash
gcloud storage buckets create gs://my-tuos-memory --location=europe-west2 --uniform-bucket-level-access
gcloud storage buckets add-iam-policy-binding gs://my-tuos-memory \
  --role=roles/storage.objectUser \
  --member=principal://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/PROJECT_ID.svc.id.goog/subject/ns/tuos/sa/tuos
```

```yaml
config:
  memory:
    storage:
      backend: gcs
      bucket: my-tuos-memory
```

To act as a Google service account instead, give that account the role, allow the Kubernetes service account to impersonate it (`roles/iam.workloadIdentityUser` for `serviceAccount:PROJECT_ID.svc.id.goog[tuos/tuos]`), and name it on the chart's service account:

```yaml
serviceAccount:
  annotations:
    iam.gke.io/gcp-service-account: tuos-memory@PROJECT_ID.iam.gserviceaccount.com
```

Outside GKE, mount a service-account key from a Secret (`kubectl create secret generic tuos-gcs-key -n tuos --from-file=key.json`) and point `GOOGLE_APPLICATION_CREDENTIALS` at it:

```yaml
extraVolumes:
  - name: gcs-key
    secret:
      secretName: tuos-gcs-key
extraVolumeMounts:
  - name: gcs-key
    mountPath: /var/run/secrets/gcs
    readOnly: true
env:
  - name: GOOGLE_APPLICATION_CREDENTIALS
    value: /var/run/secrets/gcs/key.json
```

### MinIO

The chart does not create the bucket: create it first, for example with `mc mb myminio/tuos-memory`. Add the access key to the Secret (`--from-literal=AWS_ACCESS_KEY_ID=... --from-literal=AWS_SECRET_ACCESS_KEY=...`) and the endpoint to `config`:

```yaml
config:
  memory:
    storage:
      backend: s3
      bucket: tuos-memory
      endpoint_url: http://minio.minio.svc.cluster.local:9000
```

The same settings work for AWS S3 (leave out `endpoint_url` and set `region`) and Cloudflare R2. Commands the agent runs in the pod see `AWS_*` variables (tuos passes them through to its terminal on purpose), so give this access key rights to this bucket only.

## Dashboard

By default the dashboard listens only on the pod's loopback interface, out of reach of anything outside the pod. Open it through a port-forward and browse to `http://localhost:9119`:

```bash
kubectl port-forward -n tuos pod/tuos-0 9119
```

With `dashboard.expose: true` it listens on all interfaces behind the Service `<release>-dashboard` (`dashboard.service.type` picks ClusterIP, NodePort or LoadBalancer), and it refuses to start without a login. The simplest login is a username and password in the Secret:

```bash
--from-literal=HERMES_DASHBOARD_BASIC_AUTH_USERNAME=me \
--from-literal=HERMES_DASHBOARD_BASIC_AUTH_PASSWORD='a long passphrase' \
--from-literal=HERMES_DASHBOARD_BASIC_AUTH_SECRET=$(openssl rand -base64 32)
```

A username and password suit a private network, not the open internet; [Web Dashboard → Authentication](./features/web-dashboard.md#authentication-gated-mode) covers OIDC and the other providers. Behind an Ingress or another reverse proxy, also set `dashboard.public_url` and `dashboard.trusted_proxies` in `config` ([Public URL override](./features/web-dashboard.md#public-url-override)). `dashboard.enabled: false` turns the dashboard off.

## Storage

- The volume needs block storage (`ReadWriteOnce`); the default storage classes on GKE, EKS and AKS are fine. Network filesystems such as NFS, Filestore or EFS can corrupt the SQLite sessions database ([Docker → Filesystem requirements](./docker.md#filesystem-requirements-for-statedb-in-containers)).
- Kubernetes does not let a StatefulSet change its volume settings, so `persistence.*` is fixed once installed. To grow the volume, resize the claim itself if its storage class allows expansion: `kubectl patch pvc data-tuos-0 -n tuos -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'`.
- `persistence.existingClaim` uses a claim you created. `persistence.enabled: false` uses an `emptyDir`, which loses everything when the pod is replaced.
- Back the volume up with VolumeSnapshots or your provider's disk snapshots.

## Upgrading and uninstalling

On `main`, restart the pod to pull the newest image: `kubectl rollout restart statefulset/tuos -n tuos`. To move to another tag:

```bash
helm upgrade tuos deploy/helm/tuos -n tuos --reuse-values --set image.tag=v1.2.3
```

Either way the pod is replaced; the volume and the bucket keep their contents.

`helm uninstall tuos -n tuos` removes everything except the volume's claim, `data-tuos-0`, and the bucket. Delete them yourself to remove the data: `kubectl delete pvc data-tuos-0 -n tuos`.

## Limitations

- One pod per release. For a second agent, install a second release, with its own memory `prefix` or the same one to share memory.
- The chart creates no inbound route for chat platforms. Telegram, Discord and Slack connect outwards and need none; a platform that delivers messages by webhook needs a Service and Ingress of your own.
- Several profiles in the pod work as in the [Docker image](./docker.md#multi-profile-support). With `gateway.multiplex_profiles` on, each profile reads its keys only from its own `.env` on the volume, not from the pod's environment.
- The image starts as root to prepare the volume, then runs everything as the `hermes` user (UID 10000). Other start users are not supported, so policies that require `runAsNonRoot` rule it out.
