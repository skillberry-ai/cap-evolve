Provisioning is failing on controller `east` and the errors mention
authentication. Start from job `90441`.

Read that job's log, then find what else failed on the same controller in that
window, and read the catalog configuration for the affected item.

Tell me what is actually broken and why, say how many catalog items are failing,
name the credential involved and the file it is pulled in from, and say what the
registry itself was doing.
