AAP2 job 90405 on controller east failed during a cluster provision.

Find the task that actually failed and the host it failed on. Report the
role that task belongs to.

The wait it gave up on is configured in
`ansible/configs/ocp4-cluster/default_vars.yml` in the
`agnosticd/agnosticd-v2` repository. Read that file and report how many
retries the provision was allowed.
