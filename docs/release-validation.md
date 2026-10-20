# Release validation

The RHOAI subscription is pinned to `rhods-operator.3.4.4` with manual approval.
The upstream install-operators chart approves the selected initial CSV; later
InstallPlans must not be approved automatically. The selected CSV must still be
available in the configured catalog. `startingCSV` is not a downgrade mechanism.

## Before merging

Run the Helm regression tests documented in the root README. Test the PR on a
**fresh** environment using the PR branch or exact commit for both bootstrap and
its child applications. For PR #20, the child-reference override is:

```yaml
bootstrap:
  targetRevision: fix/pin-rhoai-3.4.4
```

Do not use the repaired environment as proof that a clean RHOAI 3.4.4 installation
works: that environment retained RHOAI 3.4.5 with a temporary local MLflow image.

Verify all of the following on the fresh environment:

- Subscription approval is Manual and installed CSV is `rhods-operator.3.4.4`.
- Argo CD application controller stays Ready without OOM kills or increasing
  restart counts; application reconciliation completes. Its default memory
  request/limit is 2Gi/4Gi, configurable with `gitops.controller.resources`.
- MLflow is Available, its console and health endpoint respond, and the workshop
  user can list the intended workspace and create an experiment/trace. Check the
  deployed image for successful Kubernetes workspace and authorization plugin
  initialization, not just a successful operator installation.
- Grafana completes its Recreate rollout with its original ReadWriteOnce PVC.
- The Mortgage-AI Backend Metrics dashboard exists. Both datasource health checks
  and real metrics queries succeed; verify workshop panels with application
  traffic rather than accepting an empty dashboard.
- The Mortgage-AI API is Ready and its MLflow integration initializes.

## MLflow image override

Leave `mlflow.image.image` empty to use the image supplied by the pinned operator.
The missing Kubernetes dependency observed in the 3.4.5 image has **not** been
validated against a fresh 3.4.4 deployment. If 3.4.4 also fails, obtain and validate
a compatible maintainer/vendor-approved image before release.

An optional image override can be supplied to bootstrap and is forwarded to the
MLflow chart. The same values can be used when rendering the MLflow chart alone:

```yaml
mlflow:
  image:
    image: registry.example.com/workshop/mlflow:validated
    imagePullPolicy: IfNotPresent
```

The image above is a placeholder, not a published fix. Prefer a validated digest.
Do not publish an environment-local registry image or temporary Argo CD ignore
rules as the permanent solution.

## Grafana metrics endpoint

`rhoaiDatasource.url` defaults to the cluster Thanos endpoint, using the existing
Grafana service-account token secret. The `Bearer ${token}` template is required
in addition to the secret reference and Authorization header name.

For a separately validated dedicated endpoint, override the URL and authentication
setting in the Grafana chart values. Set `rhoaiDatasource.bearerAuth=false` only
when that endpoint genuinely does not require bearer authentication.

## Publishing v1.0.2

The bootstrap default targets `v1.0.2`. Publish that **new immutable tag** from
the reviewed release commit before consumers use this default. For bootstrap
instances tracking `main`, publish the tag from the reviewed PR head before
merging the default-reference change, or coordinate merge/tag publication while
provisioning is paused. Otherwise child applications can briefly reference a tag
that does not exist. Do not move `v1.0.1` or any existing tag. Update the consuming
catalog/deployer reference to the new tag and remove test-only branch overrides.

Merging into `main` alone does not update child applications that still target
`v1.0.1` or `1.0.0`. Tag publication and the consuming catalog reference update
are release steps; they are not performed by the templates or regression tests.
