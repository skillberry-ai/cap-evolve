In the `agnosticd/agnosticd-v2` repository, the OCP workload roles live
under `ansible/roles_ocp_workloads`. That is a directory, not a file.

Find the task file for the `ocp4_workload_pipelines_operator` role, read
it, and report how many retries the readiness wait allows and how long it
waits between attempts.
