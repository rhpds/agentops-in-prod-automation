#!/bin/bash

set -ex

NAMESPACE="${NAMESPACE:-grafana}"
USERNAME="${USERNAME:-user1}"

ROUTE=$(oc get route -n "${NAMESPACE}" grafana-route -ojsonpath='{.status.ingress[0].host}')

sed "s|\${USERNAME}|${USERNAME}|g; s|\${ROUTE}|${ROUTE}|g" /mnt/consolelink.yaml.tpl | oc apply -f-
