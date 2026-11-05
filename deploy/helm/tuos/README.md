# tuos Helm chart

Runs tuos (built on Hermes Agent) on Kubernetes: one pod running the messaging gateway, which also
runs scheduled jobs, and the web dashboard, with its state on a persistent volume.

```bash
docker build -t registry.example.com/tuos:TAG .   # from the repository root; no image is published
docker push registry.example.com/tuos:TAG

kubectl create namespace tuos
kubectl create secret generic tuos-env -n tuos --from-env-file=.env
helm install tuos deploy/helm/tuos -n tuos \
  --set image.repository=registry.example.com/tuos --set image.tag=TAG \
  --set secrets.existingSecret=tuos-env
```

`values.yaml` documents every setting. The guide, including memory in Google Cloud Storage or
MinIO and exposing the dashboard, is
[`website/docs/user-guide/kubernetes.md`](../../../website/docs/user-guide/kubernetes.md).
