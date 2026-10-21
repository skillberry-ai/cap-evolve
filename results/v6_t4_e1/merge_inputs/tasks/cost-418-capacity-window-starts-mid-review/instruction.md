It is 2026-12-02 at 11:25 UTC. I'm writing the reservation section of our
October-November 2026 cost review, and it has to cover 2026-10-01 through 2026-11-30.

Please run AWS Capacity Manager twice, both times broken down by account and reaching
back over that whole span:

1. the `unused_cost` preset, for the idle reservation cost per account and in total;
2. the `utilization` preset, for our overall reservation utilization.

Then take our EC2 spend for October and November 2026 from the cost monitor's `summary`
view, so the review can state idle reservation cost as a percentage of EC2 spend for the
two months.
