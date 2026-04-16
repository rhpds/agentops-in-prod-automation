#!/bin/bash

set -ex

NAMESPACE="${NAMESPACE:-grafana}"
USERNAME="${USERNAME:-user1}"

ROUTE=$(oc get route -n "${NAMESPACE}" grafana-route -ojsonpath='{.status.ingress[0].host}')
export ROUTE

cat << EOF | oc apply -f-
$(cat /mnt/consolelink.yaml.tpl)
  name: grafana-${USERNAME}
  href: https://${ROUTE}/
EOF
