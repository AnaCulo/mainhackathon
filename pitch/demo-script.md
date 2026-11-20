# Group Čulo · three-minute demo

The recorded cut runs about 2:45 and uses a local synthetic voice for each speaking role. The screen captures come from the checked fixture. The investigate selection is scripted in a real authenticated form. At the live pitch, a designated teammate makes that choice. All timestamps below are elapsed video time rounded to the nearest second.

### 0:00–0:15 · D

**Shot.** Deck cover. Open with the worker’s problem.

**Narration.** A worker sees two invoice totals that differ. The employer needs to acknowledge the report and assign an independent handler, without broadcasting who spoke up. This is Group Čulo's synthetic demonstration.

### 0:15–0:32 · C

**Shot.** Display Version B locally before any provider call. Show the fictional report.

**Narration.** Voice is off before a provider connects. The reporter chooses text. Our fictional report has three sentences. Two invoice totals differ. The discrepancy appeared on Monday. The ledger has both entries.

### 0:32–0:50 · A

**Shot.** Show the captured Case JSON fields from the local backend and the case reference.

**Narration.** The local backend accepts the report and builds a minimised draft. It sends only released sentences, through BRANE's live gateway, to the approved cloud model. BRANE previews show zero detections, and the completion comes back as cloud, allow, not redacted. The backend sends its real case object through the published, authenticated n8n webhook. The identity mapping stays local.

*Live rehearsal: run `n8n/demo.sh --trace --hold` and show the printed outbound check and BRANE headers.*

### 0:50–1:09 · D

**Shot.** Show the authenticated review page and the separate synthetic acknowledgement and handler email captures.

**Narration.** The handler opens the case. The report is still an allegation. Facts, timeline and evidence appear separately. The reporter's local mailbox received a neutral acknowledgement. A separate captured email tells the designated handler where to review it.

### 1:09–1:26 · D

**Shot.** Show the actual case-bound form, selected action, reason, independence affirmation, then the recorded decision.

**Narration.** This is the authorised review form. For the recording, we script the handler selecting investigate, entering a reason and confirming independence. The same form lets a person close or escalate a case. A timeout leaves the choice pending.

### 1:26–1:47 · A

**Shot.** Refresh the same case. Show feedback-demo-reminder sent, feedback unsent and both real dates.

**Narration.** The acknowledgement and substantive feedback have separate clocks. The two-minute demo reminder fired on this case after the investigation decision. The real feedback date remains February twentieth, with a February nineteenth operational target. The handler must separately approve what goes to the reporter.

### 1:47–2:11 · B

**Shot.** Show the live policy-v2 rows from `submission/MAIN_Five_Tests_Template.csv`: T4, T5, T3, and the P3a/P3b pair. In a live rehearsal, B shows the PASS/FAIL lines from `n8n/demo.sh --trace`.

**Narration.** With our policy live on BRANE, the bypass attempt is refused before any model runs. Health data stays local. Five mentions of one person become one token. An ordinary purchasing breach reaches the cloud as PERSON_01, while the forgery allegation never leaves. If any check fails, the backend returns five oh three, with zero model or webhook calls.

### 2:11–2:27 · D

**Shot.** Show the live trace timings and their quality criterion, then the manual result from `tests/manual_benchmark.py`.

**Narration.** Through the live gateway and model, the handler could open the checked brief in six to eight seconds, across four runs. The brief had the fact, the Monday timeline and the ledger evidence, with the decision pending. Our manual run took [MANUAL TIME] to the same finish line.

### 2:27–2:45 · D

**Shot.** Show the price hypothesis. Leave enough time for the last sentence.

**Narration.** At twelve cases per year, half an hour saved per case is worth three hundred thirty euros at our assumed hourly rate. A nine hundred euro pilot needs a second reason to buy. For this employer, the question is what dependable, confidential follow-up is worth.

## Rehearsal cues

Start the one-command demo with `-Hold` in advance. Let it finish the automated checks. Open the pending case whose reference the terminal printed. D can use the first 30 seconds to frame the employer’s problem while the two-minute demo timer runs. A explains the seven-day and three-calendar-month rules. B has the baseline and local test output ready. C shows the local disclosure and synthetic text. Keep credentials and terminal environment files outside the recording. Leave substantive feedback queued for human approval until after the reminder is visible.

In the recorded case, the reference is `WB-98b0095b-1675-4b1d-bf62-8739bf7cea5d`. The acknowledgement and handler capture occurred at 15:45:23 UTC. The scheduler recorded the feedback demo reminder at 15:47:26 UTC on 20 November. Each fresh rehearsal produces its own case ID. Run the manual benchmark with the same input and checks in [the business case](../docs/business-case.md). The live BRANE rerun is now available. B’s segment and the timing claims above use it, as does slide 5. **The recorded video `Culo-demo.mp4` still shows the earlier fixture run.** Re-record segments 0:32–0:50, 1:47–2:11 and 2:11–2:27, fill in [MANUAL TIME], and check the video length before upload.

