#!/bin/bash

set -ex

NAMESPACE="${NAMESPACE:-grafana}"
USERNAME="${USERNAME:-user1}"

ROUTE=$(oc get route -n "${NAMESPACE}" grafana-route -ojsonpath='{.status.ingress[0].host}')
export ROUTE USERNAME

envsubst < /mnt/consolelink.yaml.tpl | oc apply -f-
