I'd like to rename the Ansible variable `ocp4_workload_model_registry_instance_name` in `agnosticd/agnosticd-v2` to something
shorter. Two steps, please:

1. Open `ansible/roles_ocp_workloads/ocp4_workload_model_registry/defaults/main.yml` and tell me the variable's default value and the line that sets it. Cite
   the file.
2. Then search the repository for `ocp4_workload_model_registry_instance_name` to find everything else that uses it. What did
   the search return, and what does that result tell us?

Finally: is it safe to rename the variable in this role alone?
