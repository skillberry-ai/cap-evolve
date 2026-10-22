The catalog item `agd-v2.ocp4-workload-adv-dev-suite.prod` deploys the
advanced developer suite workload.

Look the catalog item up, find the AgnosticD content repository it points
at, and read the workload role's defaults file from that repository.

Report the Gitea version the workload pins, the Gitea admin user it
configures, and the pipeline operator channel it selects. Give the full
`owner/repo:path` of the file you read them from.

The workload role's defaults are at
`ansible/roles_ocp_workloads/ocp4_workload_advanced_developer_suite/defaults/main.yml`.
Read that file from whichever repository the catalog lookup names.
