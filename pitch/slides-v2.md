# Group Čulo · six-slide pitch

## 1. The clock starts when someone speaks up

A worker reports a blocked exit. Another reports a concern that would identify them by their shift alone. Both deserve a confidential route to a person.

Acknowledge receipt within seven days. Give feedback within three months of acknowledgement or, if none was sent, within three months after the seven-day period expires. Limit access to authorised people. [Directive (EU) 2019/1937, Articles 9 and 16](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=celex%3A02019L1937-20240725)

## 2. What the reporter said vs what left the building

**On the intake host** — “Two emergency exits were blocked by pallets last week. I have three photographs.” The encrypted original and its supporting details stay here.

**At the gateway** — Show T1’s exact user-message JSON. The model can select fact IDs and question IDs. The backend pins the tenant policy by SHA-256, checks that the preview matches the submitted bytes and requires zero detections. It verifies the completion headers and validates the selected IDs before rendering the brief locally.

## 3. Run the red team

The results below are from current integration tests with a simulated gateway. The panel displays the observed status, attempt count and headers on the presenter’s run. Current hosted evidence is pending.

| Synthetic input | Tested result |
| --- | --- |
| T1 · blocked exits | 200, grounded brief |
| T2 · reporter identifiers and a person-linked allegation | 202, P3, protected identifiers counted locally |
| T3 · same person five times | 200, five mentions, one case token |
| T4 · instruction in the attachment | 202, P4 |
| T5 · health details | 202, P3 |
| E1 · identifying shift and role | 202, P1 |
| E6 · contracts steered to a relative | 202, P3, five mentions kept local |
| BRANE down · simulated outage | 503, held receipt, zero gateway requests |

Each held reporter receives a case reference. The register dispatches an acknowledgement and tracks both clocks. Show the actual delivery state for the synthetic mailbox.

## 4. A person owns the decision

Open the case ID in the handler queue. For a held report the task links to the authenticated original on the intake host. Read the acknowledgement state and feedback due date. The designated handler checks for a conflict, records a decision and reason, and separately approves feedback. P6 reserves these steps for a person.

## 5. We red-teamed BRANE

| Observation in earlier direct gateway runs | What the intake code does |
| --- | --- |
| One person became both PERSON_REF_1 and PERSON_REF_2 | Counts repeated mentions under one case-scoped token before release. |
| Aliases were unlinked | Binds supplied aliases and supported surname forms locally. Ambiguous bindings trigger a hold. |
| Spoken phone digits appeared in a preview | Report text does go to the model for summaries, but only after local redaction: written and spoken phone numbers and emails, names in any case or script, staff numbers, handles and addresses are withheld first. Anything still shaped like an identifier sends the report to a person instead. |
| Names were restored in model answers | Grammar path: accepts only validated IDs and enums. Summary path: rejects any answer that adds a name, number, place or term not in the redacted text. |
| BRANE detected PERSON in our own tokens | Uses gateway tokens such as #P01, checks the preview and fails closed on detections. |

[Historical runs and findings](../docs/test-protocol.md) · [Evidence status](../submission/EVIDENCE_STATUS.md)

## 6. Measure what the buyer cares about

Historical hosted ledger runs took 6.22–7.62 seconds from submission to a usable handler page (n = 4). Manual baseline and current hosted time to first triage — **TO MEASURE**. On-time acknowledgement rate across all received cases — **TO MEASURE**. Current hosted identity-exposure check — **PENDING LIVE RUN**.

Start with Dutch 50–249 employers. Prioritise high-volume multi-entity groups and reporting platforms buying a triage add-on. Our next step is five compliance-officer interviews and a timed manual comparison. [Business case and benchmark protocol](../docs/business-case.md)
