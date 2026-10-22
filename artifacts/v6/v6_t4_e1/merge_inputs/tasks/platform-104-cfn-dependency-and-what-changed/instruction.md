The retail edge POS lab provision (job 693027 on controller `east`) failed while building its AWS stack. Its log is very large, and the controller kept only the tail.

I need two things before I relaunch it.

1. Why it failed. Read the CloudFormation template the job rendered and explain what in it causes the error. Cite the offending line as `owner/repo:path:line`.
2. What the run had already created or changed before it failed, and how many tasks changed something, so I know what to clean up first.
