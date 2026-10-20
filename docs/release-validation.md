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

`bootstrap/values.yaml` pins `mlflow.image.image` to the RHOAI 3.4.4
`odh-mlflow-rhel9` digest (`sha256:fe4719b7...`) by default. The 3.4.5 rebuild of
this image dropped the `kubernetes` Python package, which the operator's
unconditional `--workspace-store-uri=kubernetes://` server flag depends on;
MLflow crashes on startup with `UnsupportedWorkspaceStoreURIException` before it
ever serves. Confirmed live against both digests during a production incident
(see the linked Slack thread in `bootstrap/values.yaml`'s comment) - this is not
a placeholder, it is the validated fix. Same MLflow version either way
(`3.10.1+rhaiv.3`), so this is a safe default while pinned to `stable-3.4`.

This override can be supplied to bootstrap and is forwarded to the MLflow chart.
The same values can be used when rendering the MLflow chart alone:

```yaml
mlflow:
  image:
    image: registry.redhat.io/rhoai/odh-mlflow-rhel9@sha256:fe4719b7cb5094a81bca1a06a3cf0ea266f2f10ccff4096b420e1ae678a2d503
    imagePullPolicy: IfNotPresent
```

Re-validate this digest (or obtain a new one) before bumping the RHOAI channel -
e.g. to `stable-3.5` - since the dependency gap is specific to the 3.4.5 image
and may not apply, or may recur differently, in later releases. Do not publish
an environment-local registry image or temporary Argo CD ignore rules as the
permanent solution.

### Recovering an already-drifted cluster

Pinning the operator (above) does not repair a cluster that already upgraded to
the broken 3.4.5 image - the Subscription/CSV pin only prevents *future*
drift, and the bad image comes from the operator's `RELATED_IMAGE`, not from an
ArgoCD-managed resource, so `argocd app sync` cannot fix it either. To recover a
live cluster already stuck on the broken image:

```bash
GOOD='registry.redhat.io/rhoai/odh-mlflow-rhel9@sha256:fe4719b7cb5094a81bca1a06a3cf0ea266f2f10ccff4096b420e1ae678a2d503'
oc patch applications.argoproj.io mlflow -n openshift-gitops --type=merge -p '{"spec":{"syncPolicy":{"automated":null}}}'
oc patch mlflow mlflow --type=merge -p '{"spec":{"image":{"image":"'"$GOOD"'","imagePullPolicy":"IfNotPresent"}}}'
oc rollout status deploy/mlflow -n redhat-ods-applications --timeout=5m
oc get mlflow mlflow -o jsonpath='{.status.conditions[?(@.type=="Available")].status} {.status.url}{"\n"}'
```

The `syncPolicy.automated: null` patch is required first - `mlflow`'s
`selfHeal: true` will otherwise revert the image patch on the next reconcile.
Once MLflow is `Available`, restart the mortgage app so it picks up the
now-running MLflow (it will not emit traces until this runs, even though the
app itself stays healthy):

```bash
oc rollout restart deploy/mortgage-ai-api -n wksp-user1
```
MLflow is a cluster-scoped singleton, so this is one patch per cluster
regardless of per-user seat count; the mortgage restart is per-namespace/seat.

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
