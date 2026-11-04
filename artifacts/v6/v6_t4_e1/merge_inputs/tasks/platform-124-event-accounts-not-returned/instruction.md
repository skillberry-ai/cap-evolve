The Adriatic Summit event finished on 2026-09-26. Every AWS sandbox account reserved for
it (reservation `adriatic-summit-2609` in the sandbox account database) should have been
cleaned up and handed back to the pool by now.

Check which of those accounts are still not available. For each one, track down its
cleanup (destroy) job in AAP2 and tell me why the account hasn't come back, so I know
what to do to get each one returned.
