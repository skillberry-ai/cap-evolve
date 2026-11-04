Attendees of the NetBox automation lab report that its database volume fills up during
module 2. The lab's catalog item is `network_bu/netbox-automation-lab/common.yaml` in `rhpds/agnosticv`, and it already asks
for a 60 GiB database. On 2026-11-03 the item was moved to a newer `agnosticd/agnosticd-v2`
release. Its workload role keeps its defaults in `ansible/roles_ocp_workloads/ocp4_workload_netbox_ipam/defaults/main.yml`.

Read the catalog item, then the role's defaults at the release the item now deploys, and tell
me:

1. Which agnosticd-v2 release the item deploys.
2. How big the database volume is for new orders, and whether our 60 GiB setting is
   honoured. Cite the line in the role's defaults that decides it.
3. Exactly what to put in the catalog item to get 60 GiB.
