# Buying a confidential reporting channel in the Netherlands

**Decision for a pilot, 20 November 2026.** A compliance director at a Dutch employer with 50–249 workers could use Čulo to prepare an unverified brief, register receipt and keep an independent handler’s follow-up visible. The employer still needs a designated handler, an alternate for conflicts and a safe way to reach the reporter. The synthetic prototype can demonstrate that division of work. Procurement for live reports requires additional safeguards.

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

Vendor figures checked 20 November 2026. Loaded HR cost of €55 per hour, case volume and staff times are planning assumptions. Vendor and proposed prices exclude any unpriced services. Under these assumptions the pilot saves 6 staff hours (€330/year) but costs €570 more than the internal option. At 30 minutes saved per case, €900 ÷ €27.50 = 32.7, or **33 cases/year** to cover the fee from labour savings alone. At six cases per year the labour saving falls to €165. Interview buyers about the value of traceable follow-up and the cost of covering absences. [Whistlelink pricing and inclusions](https://www.whistlelink.com/pricing/)

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

**Observed automated runs, n = 2:** 143 ms and 86 ms (range 86–143 ms). Each started before POST /reports and ended after fetching the authenticated handler page and checking its contents. Both used Person B’s running service, exact-fixture local check/model doubles, the published n8n webhook, and a durable case register. Network services were on the same machine. Excludes drafting the input, notification latency, live BRANE/model latency, human review and a cold production start. The recording follows the 86 ms case. Use `node n8n/walkthrough.mjs` with the demo environment to repeat.

Four later integration regression runs used the same timer and returned 179, 173, 133 and 166 ms. Across all six runs the observed range was 86–179 ms. The pitch and rough video report the two recorded benchmark runs.

**Manual comparison pending.** Give the same text to a teammate who has not seen the prepared brief. Supply a blank restricted case form and the same four checks. Have a second person start the timer on release and stop it on successful handler access. Record minutes/seconds, missing facts, any corrections and sample size. Repeat failed quality checks with the clock running. Report observed differences only after this exercise. The 30-minute illustrative saving above is a pricing sensitivity assumption.

