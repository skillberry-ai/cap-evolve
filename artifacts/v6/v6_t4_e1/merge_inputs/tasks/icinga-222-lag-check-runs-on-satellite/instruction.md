Since 2026-12-07 our reporting app, which reads from the PostgreSQL hot standby
`pgsql-rep-ams-07`, has been showing figures hours behind the primary. Yet Icinga's `pg-standby-lag`
check on that host has said replay lag 0 s and been OK the whole time, and I don't trust it.
The plugin is in `rhpds/rhdp-monitoring` at the path in the service vars. Explain where that
0 s comes from: which machine actually runs the check, and which PostgreSQL server does it
read? And what is the standby's real replay lag? (It is 2026-12-08, 09:00 UTC.)
