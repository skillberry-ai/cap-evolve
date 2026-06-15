# Optimizer scratchpad

## Diagnosis (iteration 1)

Key failure patterns identified from baseline (val reward 0.460):

1. **Task 3 (missed get_user_details)**: Agent didn't call get_user_details to look up profile info. Added "General Workflow Principles" section emphasizing always looking up user details early.

2. **Task 7 (multi-reservation handling)**: Agent failed to handle 5 actions across multiple reservations. Added principle about handling multi-step requests completely.

3. **Task 10 (flight date change)**: Agent got stuck on flight modification workflow. Added explicit workflow steps for changing flights to a new date.

4. **Task 11 (basic economy cabin change)**: Agent refused update_reservation_flights with cabin='basic_economy' — confused "basic economy flights can't be modified" rule (which means can't change flights WHEN already basic economy) with changing cabin TO basic economy. Clarified policy wording and update_reservation_flights docstring.

5. **Task 12 (calculate + baggage)**: Agent didn't use calculate tool for price math or update_reservation_baggages. Added emphasis on using calculate tool and improved baggage tool docstring.

## Changes made (iteration 1):
- policy.md: Added "General Workflow Principles" section (4 rules)
- policy.md: Clarified "Change flights" section re: basic economy
- policy.md: Expanded "Change cabin" section with API usage and calculate tool guidance
- policy.md: Added workflow steps under "Modify flight"
- policy.md: Expanded "Change baggage" section
- policy.md: Clarified payment section for cabin changes
- tools.py: Improved get_user_details docstring (emphasize calling early)
- tools.py: Improved calculate docstring (examples of when to use)
- tools.py: Rewrote update_reservation_flights docstring (dual purpose: flights + cabin)
- tools.py: Improved update_reservation_baggages docstring (free bag rules, usage)
- tools.py: Improved get_reservation_details docstring (call for each reservation)
- tools.py: Improved search_direct_flight docstring (use case clarity)

## Diagnosis (iteration 3)

Current val: 0.680. Cand_0002 was rejected (-0.09) for being too aggressive.

### Still-failing tasks:
- **Task 7 (5/5 missed)**: Agent still not looking up multiple reservations and processing them all
- **Task 11 (1/1 missed)**: Agent still refusing cabin downgrade to basic_economy despite policy
- **Task 14 (2/2 missed)**: Agent not executing cancel + new booking when user explicitly asks

### Why cand_0002 failed (val 0.590):
- Added a full "Cancel and Rebook" section (too aggressive, caused unwanted cancellations)
- Added rule "cancel and rebook when modification not possible" (triggered cancellations for modifiable reservations)
- Overly emphatic wording that made agent too aggressive on working tasks
- Expanded "Change flights" with simultaneous cabin+flight language that confused the model

### Strategy for cand_0003:
1. For task 7: Strengthen multi-reservation lookup + processing guidance
2. For task 11: Add explicit "NEVER refuse a cabin downgrade to basic_economy" statement
3. For task 14: Clarify that if user asks to cancel + book new, just verify criteria and do it
4. Do NOT add a "Cancel and Rebook" section (that broke cand_0002)
5. Keep changes brief and integrated
6. Make agent more action-oriented (less likely to transfer/refuse valid requests)

## Diagnosis (iteration 7)

Current val: 0.715. Cand_0004-0006 all rejected (no significant improvement).

### Still-failing tasks from train set:
- **Task 11 (1/1 missed)**: update_reservation_flights with cabin='basic_economy' — agent STILL refusing despite "NEVER refuse" language. This is the most stubborn failure.
- **Task 14 (2/2 missed)**: cancel_reservation + book_reservation — user wants JFK→SFO (different dest). Agent not doing cancel+rebook despite policy principle #5.
- **Task 18 (5/5 missed)**: Complex multi-step: flight changes + cabin + passengers + bags. Agent likely stops after first action or runs out of turns asking confirmations one by one.

### Strategy for cand_0007:
1. For task 11: Added even stronger CRITICAL language about cabin='basic_economy' being valid in both policy AND tool docstring. Explicitly separated the concepts.
2. For task 14: Added principle #8 "Cancel and rebook when modification is impossible" (integrated, not a full section). Strengthened cancel_reservation tool doc. Added guidance in transfer_to_human_agents about what NOT to transfer.
3. For task 18: Added "Handling multiple changes to one reservation" section with explicit ordering. Added batched confirmation guidance to avoid running out of turns.
4. General: Made confirmation batching explicit (present all changes, get one "yes", execute sequentially).
5. Avoided being overly aggressive (lesson from cand_0002).
