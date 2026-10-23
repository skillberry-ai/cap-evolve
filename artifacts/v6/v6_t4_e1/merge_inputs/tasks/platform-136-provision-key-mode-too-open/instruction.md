Provisioning of the sensor gateway workshop for GUID qz7hd died in job 552816 on the `east` AAP2 controller. The last thing in the log is `Permission denied (publickey)` from the bastion, and a colleague wants to rotate the EC2 key pair before we order again.

Before anyone touches keys, tell me what made the SSH connection fail, which task in the content set that up, and what should change in that task. Read that task's file in the repository the job ran from, and cite the offending line as `owner/repo:path:line`.
