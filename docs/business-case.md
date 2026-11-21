# Buying a confidential reporting channel in the Netherlands

**What the employer pays for.** On labour alone Čulo does not pay for itself: at 12 reports a year it costs €570 more than an internal process, and it breaks even only at 33 reports (see below). The case for buying is legal and confidential:
- **Deadline compliance.** Every report, including one held for a person, is registered on receipt. The seven-day acknowledgement and three-month feedback clocks never depend on the model succeeding.
- **Confidentiality towards the AI vendor.** Identities, contact details, health data and person-linked criminal allegations stay on the employer's host. In the 21 Nov live runs no protected identifier appeared in any model-bound message (`evidence/backend_run_20261121-004849.json`, `evidence/backend_run_20261121-005741.json`).

Price the pilot against the cost of a missed deadline or an identity leak, not against staff minutes.

**Decision for a pilot, 20 November 2026.** A compliance director at a Dutch employer with 50–249 workers could use Čulo to prepare an unverified brief, register receipt and keep an independent handler’s follow-up visible. The employer still needs a designated handler, an alternate for conflicts and a safe way to reach the reporter. The synthetic prototype can demonstrate that division of work. Procurement for live reports requires additional safeguards.

## Who buys this

Čulo is an AI triage layer for an existing reporting channel. A compliance team can prepare a first brief without showing the report to the AI vendor. The intake host retains the original. The model can select from allowlisted facts after the gateway checks pass.

The first legal beachhead is Dutch employers with 50–249 workers. For a commercial pilot, recruit a multi-entity group with a central ethics team, or a whistleblowing platform that can sell triage as an add-on. Ask each buyer how many reports reach the same intake team across its entities or customers. The case-volume sensitivity below makes that question material.

| Pilot measure | Observable result |
| --- | --- |
| Acknowledgement-deadline compliance | Count all received cases, including holds. Divide acknowledgements actually delivered within seven days by cases due. Keep missed or unreachable deliveries visible. |
| Zero identity exposure to model vendors | Compare the synthetic identifiers against recorded model-bound user messages. Inspect the BRANE preview and route headers for completed requests and count completion attempts on holds. Report the tested cases and gaps in live coverage. |
| Time to first triage | Time from release of the report until the designated handler can open a usable brief or a held-review task. Record quality and report the two paths separately. |

Willingness to pay is unvalidated. Interview five compliance officers about annual volume, missed acknowledgements, preparation time and purchasing authority. Ask them to walk through a recent workflow using synthetic details before discussing pilot pricing.

## What the employer buys

A worker who spots mismatched invoices may want an independent person to check the ledger without revealing who spoke up to colleagues or the person named. Today somebody must read the account, distinguish allegation from fact, strip identifying details, record receipt, acknowledge it, assign the case and track the feedback date. A general HR inbox makes it difficult to control who sees each item.

The prototype prepares facts, timeline and evidence for review. A local register deduplicates deliveries, creates the approval task and records neutral outbound messages. A handler chooses whether to investigate, close or escalate, supplies the reason, checks conflicts and separately approves the substantive update. Investigation, advice, interviews and evidence assessment still consume professional time.

Under the Dutch Wbk the general threshold is 50 statutory workers. Paid subordinate workers can count beyond payroll employees. Covered financial-sector and other specified EU-instrument employers can qualify below 50. Private employers with 50–249 workers may share resources while retaining duties. A buyer must verify its legal entity, worker count and sector. Written intake alone does not supply the full oral and meeting procedure. For live operation the employer also needs an independent alternate, lawful access to originals, a safe return route, processing agreements, retention controls, and an assessment of risks and transfers. [Dutch employer guidance](https://www.huisvoorklokkenluiders.nl/wet-en-regelgeving/informatie-voor-werkgevers) · [Person A’s legal analysis](https://github.com/AnaCulo/mainhackathon/blob/a89e570/docs/legal-research.md)

## Alternatives and cost

| Option | Annual cost for an illustrative employer | Work and coverage |
|---|---:|---|
| External hotline platform | Whistlelink publishes €99/month for 50–149 employees (€1,188/year) and €149/month for 150–249 (€1,788/year). For 1,000+ it requests contact and publishes no price. | Published package includes a 24/7 voice hotline, anonymous two-way communication and case management. The price of a separately staffed investigation is unverified. |
| Internal HR or compliance process | 12 reports × (45 min preparation + 30 min review) × €55/hour = **€825/year** | Assumes a restricted intake channel already exists. Training, coverage, ongoing readiness and investigation are additional. Dedicated access, confidentiality and cover during absence still need an owner. |
| Čulo pilot price hypothesis | €75/month = €900/year plus 12 × (15 min preparation + 30 min review) × €55/hour = **€1,395/year** | Illustrative employer handles 12 reports annually. The 15 minutes include checking omissions and releasing the draft. The handler retains the same 30 minutes of initial review. The demo uses synthetic delivery and text. |

Vendor figures checked 20 November 2026. Loaded HR cost of €55 per hour, case volume and staff times are planning assumptions. Vendor and proposed prices exclude any unpriced services. Under these assumptions the pilot saves 6 staff hours (€330/year) but costs €570 more than the internal option. At 30 minutes saved per case, €900 ÷ €27.50 = 32.7, or **33 cases/year** to cover the fee from labour savings alone. At six cases per year the labour saving falls to €165. Labour savings therefore do not justify the fee for this employer. The pitch claims deadline compliance and confidentiality instead. Interview buyers about the value of traceable follow-up and the cost of covering absences. [Whistlelink pricing and inclusions](https://www.whistlelink.com/pricing/)

Illustrative annual supplier costs per customer include €120 allocated hosting and encrypted backup, €60 processing, and two support hours at €55 (€110). €900 − €290 = €610 contribution before sales, implementation, incident response, legal review, tax and fixed development. Neither cost nor willingness to pay has been measured. Shared deployment and safeguarding costs can materially change this figure.

## How many employers could the service reach?

| Geography and period | Published unit and coverage | Interpretation |
|---|---|---|
| Netherlands, start Q4 2026 (provisional) | **9,515** medium enterprises, 50–249 workers, in the CBS business economy. Table reports **9.515 thousand**. | Beachhead proxy. Excludes larger firms, smaller regulated entities and employers outside the covered business economy. |
| EU including NL, 2023 (preliminary release) | **246,000** medium enterprises with 50–249 persons employed and **53,000** large with 250+, in Eurostat’s EU business economy. | Rounded total **299,000** at 50+. EU figure includes the Netherlands. Different years and statistical coverage preclude subtracting the NL count to size other member states. |

Statistical enterprises and persons employed differ from responsible legal employers and the Wbk worker test. These figures describe the pool for customer discovery. Exact legally eligible counts, shared reporting arrangements, high-volume segments and incumbent contract renewals are unknown. [CBS Q4 2026 size-band table](https://www.cbs.nl/en-gb/news/2026/47/number-of-smes-has-risen-by-more-than-a-quarter-since-2021) · [Eurostat 2023 release](https://ec.europa.eu/eurostat/de/web/products-eurostat-news/w/ddn-20241205-1)

For the Netherlands, assume one quarter of the 9,515 firms have an independent handler, a compatible protected channel and a purchase window. Floor(9,515 × 25%) = **2,378 serviceable customers**. At €900/year that is €2,140,200 of potential annual subscriptions. Winning 2% of that segment, rounded down to 47 customers, gives **€42,300 annual recurring revenue**. For EU context only, the same hypothetical 25% filter on 246,000 medium firms gives 61,500 and €55.35m/year. Language, national rules and local support would require separate validation. These are scenarios, not forecasts.

## A benchmark the jury can repeat

Use exactly “Two invoice totals differ. The discrepancy appeared on Monday. The ledger has both entries.” Start on release of the text to the preparer or submission to the endpoint. Finish when the assigned handler can open the case. Check the handler view for the reported discrepancy, Monday timeline, ledger evidence and a pending human decision, with no invented person or conclusion.

Automated runs against local test doubles (86–179 ms) only checked the plumbing. They exclude BRANE and the model, and they are not compared with a person anywhere.

**Observed live runs through hosted BRANE, n = 4:** **7.62, 6.33, 7.16 and 6.22 s**, range 6.2–7.6 s. The timer and finish line are the same as above. These runs used the Python backend (`backend/app`) with the real BRANE gateway (policy-v2, pinned fingerprint), the real cloud model `openrouter:openai/gpt-6-luna`, the published n8n webhook and the case register, all on one machine apart from BRANE and the model. Every handler view showed every required field:
- reported fact: *"The report describes a discrepancy between invoice totals."*
- timeline: *Monday*
- evidence: *ledger entries, original held locally*
- *Human decision · pending*
- no person or conclusion added

Every trace also records:
- the outbound text, previewed at BRANE: route cloud, zero detections, payload identical to what the backend sent
- the completion headers: `Routed-To: cloud`, `Redacted: false`
- a decision of "investigate", recorded afterwards through the handler form (scripted for evidence; a person clicks it in the demo)

**Use these live numbers for any claim about the deployed path.** The table below compares them with an **estimate** of the same work by hand. No person has been timed yet. Evidence: `evidence/live_trace_20261120-172546.json`, `-172635.json`, `-173954.json` and `-174739.json`. The last run used the minimised payload (category and summary only). Repeat with `n8n/demo.sh --trace`, which needs Node 24 and `backend/.env` with the team key and pinned fingerprint.

**Manual comparison: estimated, not yet measured.** `scripts/estimate_manual_baseline.py` simulates the protocol 10,000 times. It uses published typing speed (Dhakal et al., CHI 2018: 51.6 wpm average), the slower pace of composing text (Karat et al., CHI 1999), reading speed (Brysbaert, 2019: 238 wpm) and the keystroke-level model (Card, Moran & Newell, 1983). Result: about 2 minutes by hand (median 123 s, 90% of runs 1.6–3.3 min), roughly 18 times the agent's median of 6.75 s, on a three-sentence report ([estimate](../evidence/manual_baseline_estimate.json)). Longer real reports take more. To replace the estimate with a measurement, run `python3 tests/manual_benchmark.py`, which follows this protocol, times the run and compares it with the live traces. Give the same text to a teammate who has not seen the prepared brief. Supply a blank restricted case form and the same four checks. Have a second person start the timer on release and stop it on successful handler access. Record minutes/seconds, missing facts, any corrections and sample size. Repeat failed quality checks with the clock running. Report observed differences only after this exercise. The 30-minute illustrative saving above is a pricing sensitivity assumption.


## Manual baseline vs Čulo

| Input | Manual minutes (n, range) | Čulo seconds (n, range) | Quality checks passed |
| --- | --- | --- | --- |
| Ledger discrepancy, Monday, ledger entries | **Estimated, not measured:** median 2.0 min, 90% of simulated runs 1.6–3.3 min (`scripts/estimate_manual_baseline.py`). Timed run with two teammates pending (`tests/manual_benchmark.py`) | Hosted runs, n = 4, 6.22–7.62 s (20 Nov build). This report takes the same fixed-grammar path on the current build | Historical handler pages showed discrepancy, Monday, ledger evidence and pending human decision. No invented person or conclusion. |
| Held report with identifying shift details (E1) | Not measured; the script covers the ledger case only | Held locally before any BRANE call in the 21 Nov live run. End-to-end timing not recorded | Current local tests check a P1 receipt, register handoff and zero gateway requests. End-to-end timing pending. |
