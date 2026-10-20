# AgentOps in Production - Automation

GitOps automation for deploying the **AgentOps in Production: Agentic End-to-End Observability with Red Hat AI** workshop infrastructure on OpenShift using Helm and ArgoCD.

## Related Repositories

| Repository | Description |
|------------|-------------|
| [agentops-in-prod-showroom](https://github.com/rhpds/agentops-in-prod-showroom) | Workshop content and lab instructions (Showroom) |
| [multi-agent-loan-origination](https://github.com/rh-ai-quickstart/multi-agent-loan-origination) | Multi-agent mortgage lending application deployed by this automation |

## Architecture

This repo implements an **app-of-apps** pattern: a single bootstrap Helm chart generates ArgoCD Applications that deploy the full stack per user.

```
bootstrap/                         # ArgoCD app-of-apps parent chart
├── values.yaml                    # User count, cluster domain, repo URL
└── templates/
    ├── workspace.yaml             # Per-user namespace + RBAC (ApplicationSet)
    ├── mortgage-ai.yaml           # Per-user mortgage-ai stack (ApplicationSet)
    ├── grafana.yaml               # Observability dashboards
    ├── mlflow.yaml                # MLflow tracking server
    ├── minio.yaml                 # Object storage
    ├── dspa.yaml                  # Data Science Pipelines
    ├── openshift-ai-operator.yaml # RHOAI operator
    ├── openshift-ai.yaml          # RHOAI instance
    ├── cluster-monitoring.yaml    # User workload monitoring
    ├── logging.yaml               # Cluster logging
    └── image-puller.yaml          # DS notebook image pre-puller

deployments/                       # Individual Helm charts
├── mortgage-ai/                   # Full mortgage-ai stack (API, UI, DB, Keycloak, MinIO, LlamaStack)
├── workspace/                     # Per-user namespace, RBAC, LLM secrets
├── grafana/                       # Grafana operator, dashboards, datasources
├── mlflow/                        # MLflow tracking server
├── minio/                         # MinIO object storage
├── dspa/                          # Data Science Pipelines Application
├── openshift-ai/                  # RHOAI DataScienceCluster
├── openshift-ai-operator/         # RHOAI operator subscription
├── cluster-monitoring/            # OpenShift monitoring config
├── logging/                       # Cluster logging stack
└── image-puller/                  # DaemonSet for pre-pulling notebook images
```

## What Gets Deployed

Each workshop user (`user1`..`userN`) gets an isolated namespace (`wksp-userX`) with:

- **Mortgage AI application** -- multi-agent loan origination system (API + UI + PostgreSQL/pgvector + Keycloak + MinIO)
- **MLflow** -- experiment tracking and agent trace observability
- **Grafana dashboards** -- LLM token usage, inference latency, agent performance metrics
- **Data Science Pipelines** -- Kubeflow Pipelines for ML workflows
- **OpenShift AI** -- model serving, notebooks, and platform ML tooling

## Validation and release

See [release validation](docs/release-validation.md) before publishing a new catalog
release. Merging a PR does not update child applications pinned to an older tag,
and a `startingCSV` does not downgrade an already-installed operator.

Run the Helm regression tests locally (Helm and Python 3 are required):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -B -m unittest discover -s tests -v
```
