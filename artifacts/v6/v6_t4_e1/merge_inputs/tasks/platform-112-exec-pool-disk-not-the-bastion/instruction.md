An Edge AI Inference Lab provision, AAP2 job `2817734` on controller `west`, failed
while unpacking the OpenShift installer with "No space left on device". A colleague
says the lab's bastion filled up and has opened a change to raise the bastion volume
size in the catalog item.

Before that merges, confirm the diagnosis. Read the job log, check the item's config,
and look at the controller's own logs. Tell me what actually ran out of space and why
it happened, how many jobs it has failed so far, and whether that change would help.
