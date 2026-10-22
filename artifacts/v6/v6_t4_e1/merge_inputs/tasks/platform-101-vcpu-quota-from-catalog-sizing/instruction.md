Our lakehouse benchmark lab will not come up. The last attempt was provision job 238114 on the `west` AAP2 controller, and AWS refused part of the stack.

I need to know what AWS refused, how much the account allows, and how many vCPUs the catalog item asks for in total. Then explain why the request overflowed it. The instance sizing for this lab is set in its agnosticv catalog item, so find that item and read its configuration.

Cite the line that sets the worker instance size as `owner/repo:path:line`. Finish with one root-cause category and your confidence.
