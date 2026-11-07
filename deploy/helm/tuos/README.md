# tuos Helm chart

Runs tuos (built on Hermes Agent) on Kubernetes: one pod running the messaging gateway, which also
runs scheduled jobs, and the web dashboard, with its state on a persistent volume.

```bash
kubectl create namespace tuos
kubectl create secret generic tuos-env -n tuos --from-env-file=.env
helm install tuos deploy/helm/tuos -n tuos --set secrets.existingSecret=tuos-env
```

It runs the image this repository publishes, `ghcr.io/sreent/tuos:main`; set `image.tag` to a release
tag to pin one, or `image.repository` and `image.tag` to run your own build.

`values.yaml` documents every setting. The guide, including memory in Google Cloud Storage or
MinIO and exposing the dashboard, is
[`website/docs/user-guide/kubernetes.md`](../../../website/docs/user-guide/kubernetes.md).
