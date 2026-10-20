"""Regression coverage for GPTEINFRA-18270; renders charts without cluster access."""
import functools
import pathlib
import shutil
import subprocess
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
THANOS_URL = "https://thanos-querier.openshift-monitoring.svc:9091"
TEST_IMAGE = "registry.example.com/workshop/mlflow:validated"


@functools.lru_cache(maxsize=None)
def render(chart, namespace="wksp-user1", overrides=()):
    command = ["helm", "template", "regression", str(ROOT / chart),
               "--namespace", namespace]
    for value in overrides:
        command.extend(["--set", value])
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def resource(documents, kind, name):
    return next(doc for doc in documents
                if doc["kind"] == kind and doc["metadata"]["name"] == name)


def sources(documents):
    for doc in documents:
        if doc["kind"] == "Application":
            spec = doc["spec"]
        elif doc["kind"] == "ApplicationSet":
            spec = doc["spec"]["template"]["spec"]
        else:
            continue
        if "source" in spec:
            yield spec["source"]
        yield from spec.get("sources", [])


@unittest.skipUnless(shutil.which("helm"), "Helm must be installed")
class BootstrapTests(unittest.TestCase):
    def test_application_controller_has_memory_headroom(self):
        argo = resource(render("bootstrap"), "ArgoCD", "openshift-gitops")
        resources = argo["spec"]["controller"]["resources"]
        self.assertEqual(resources["requests"]["memory"], "2Gi")
        self.assertEqual(resources["limits"]["memory"], "4Gi")
        self.assertIn("applicationSet", argo["spec"])

    def test_controller_resources_can_be_overridden(self):
        argo = resource(render("bootstrap", overrides=(
            "gitops.controller.resources.limits.memory=6Gi",
        )), "ArgoCD", "openshift-gitops")
        self.assertEqual(argo["spec"]["controller"]["resources"]["limits"]["memory"], "6Gi")

    def test_release_reference_reaches_all_repository_children(self):
        repo = "https://github.com/rhpds/agentops-in-prod-automation"
        child_sources = [s for s in sources(render("bootstrap")) if s["repoURL"] == repo]
        self.assertGreater(len(child_sources), 5)
        self.assertTrue(all(s["targetRevision"] == "v1.0.2" for s in child_sources))

    def test_pr_reference_can_be_used_for_premerge_testing(self):
        repo = "https://github.com/rhpds/agentops-in-prod-automation"
        branch = "fix/pin-rhoai-3.4.4"
        docs = render("bootstrap", overrides=("bootstrap.targetRevision=" + branch,))
        child_sources = [s for s in sources(docs) if s["repoURL"] == repo]
        self.assertTrue(all(s["targetRevision"] == branch for s in child_sources))

    def test_mlflow_uses_operator_image_by_default(self):
        app = resource(render("bootstrap"), "Application", "mlflow")
        self.assertNotIn("helm", app["spec"]["source"])

    def test_mlflow_image_override_is_forwarded(self):
        app = resource(render("bootstrap", overrides=(
            "mlflow.image.image=" + TEST_IMAGE,
            "mlflow.image.imagePullPolicy=Always",
        )), "Application", "mlflow")
        image = app["spec"]["source"]["helm"]["valuesObject"]["mlflow"]["image"]
        self.assertEqual(image, {"image": TEST_IMAGE, "imagePullPolicy": "Always"})

    def test_multiple_workshop_users_are_preserved(self):
        docs = render("bootstrap", overrides=("user.count=3",))
        appset = resource(docs, "ApplicationSet", "grafana")
        elements = appset["spec"]["generators"][0]["list"]["elements"]
        self.assertEqual([e["user"] for e in elements], ["user1", "user2", "user3"])


@unittest.skipUnless(shutil.which("helm"), "Helm must be installed")
class GrafanaTests(unittest.TestCase):
    def test_recreate_strategy_preserves_rwo_storage(self):
        grafana = resource(render("deployments/grafana"), "Grafana", "grafana")
        self.assertEqual(grafana["spec"]["deployment"]["spec"]["strategy"]["type"], "Recreate")
        pvc = grafana["spec"]["persistentVolumeClaim"]["spec"]
        self.assertEqual(pvc["accessModes"], ["ReadWriteOnce"])

    def test_rhoai_datasource_has_complete_bearer_auth(self):
        datasource = resource(render("deployments/grafana"), "GrafanaDatasource", "rhoai-prometheus")["spec"]
        self.assertEqual(datasource["datasource"]["url"], THANOS_URL)
        self.assertEqual(datasource["datasource"]["jsonData"]["httpHeaderName1"], "Authorization")
        self.assertEqual(datasource["datasource"]["secureJsonData"]["httpHeaderValue1"], "Bearer ${token}")
        self.assertEqual(datasource["valuesFrom"], [{
            "targetPath": "secureJsonData.httpHeaderValue1",
            "valueFrom": {"secretKeyRef": {"name": "grafana-auth-secret", "key": "token"}},
        }])

    def test_rhoai_endpoint_and_auth_are_configurable(self):
        docs = render("deployments/grafana", overrides=(
            "rhoaiDatasource.url=https://validated-prometheus.example.com:9090",
            "rhoaiDatasource.bearerAuth=false",
        ))
        datasource = resource(docs, "GrafanaDatasource", "rhoai-prometheus")["spec"]
        self.assertEqual(datasource["datasource"]["url"], "https://validated-prometheus.example.com:9090")
        self.assertNotIn("valuesFrom", datasource)
        self.assertNotIn("secureJsonData", datasource["datasource"])
        self.assertNotIn("httpHeaderName1", datasource["datasource"]["jsonData"])

    def test_existing_workshop_dashboard_and_datasource_are_preserved(self):
        docs = render("deployments/grafana")
        dashboard = resource(docs, "GrafanaDashboard", "mortgage-ai-backend")
        self.assertIn("Mortgage-AI Backend Metrics", dashboard["spec"]["json"])
        datasource = resource(docs, "GrafanaDatasource", "user-workload-monitoring")
        self.assertTrue(datasource["spec"]["datasource"]["isDefault"])


@unittest.skipUnless(shutil.which("helm"), "Helm must be installed")
class MLflowTests(unittest.TestCase):
    def test_no_environment_specific_image_is_enabled_by_default(self):
        mlflow = resource(render("deployments/mlflow"), "MLflow", "mlflow")
        self.assertNotIn("image", mlflow["spec"])
        self.assertEqual(mlflow["spec"]["backendStoreUri"], "sqlite:////mlflow/mlflow.db")
        self.assertEqual(mlflow["spec"]["storage"]["resources"]["requests"]["storage"], "100Gi")

    def test_validated_image_can_be_overridden(self):
        mlflow = resource(render("deployments/mlflow", overrides=(
            "mlflow.image.image=" + TEST_IMAGE,
        )), "MLflow", "mlflow")
        self.assertEqual(mlflow["spec"]["image"], {
            "image": TEST_IMAGE, "imagePullPolicy": "IfNotPresent",
        })

    def test_bootstrap_override_renders_in_child_chart(self):
        app = resource(render("bootstrap", overrides=(
            "mlflow.image.image=" + TEST_IMAGE,
        )), "Application", "mlflow")
        image = app["spec"]["source"]["helm"]["valuesObject"]["mlflow"]["image"]
        mlflow = resource(render("deployments/mlflow", overrides=(
            "mlflow.image.image=" + image["image"],
            "mlflow.image.imagePullPolicy=" + image["imagePullPolicy"],
        )), "MLflow", "mlflow")
        self.assertEqual(mlflow["spec"]["image"], image)


class OperatorPinTests(unittest.TestCase):
    def test_rhoai_344_requires_manual_approval(self):
        with (ROOT / "deployments/openshift-ai-operator/values.yaml").open() as stream:
            operator = yaml.safe_load(stream)["operators"]["rhods-operator"]
        self.assertEqual(operator["channel"], "stable-3.4")
        self.assertEqual(operator["installPlanApproval"], "Manual")
        self.assertEqual(operator["startingCSV"], "rhods-operator.3.4.4")


if __name__ == "__main__":
    unittest.main()
