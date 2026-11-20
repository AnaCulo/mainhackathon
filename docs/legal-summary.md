# Legal summary (one page)

Assessment date: 20 November 2026. This is a summary of the [full legal research](legal-research.md). It is written for the jury and is not legal advice.

## What the law asks of an employer's internal channel
- **Receipt and follow-up deadlines:** acknowledge within seven days and give feedback within three months. A designated, independent person follows up. (Directive (EU) 2019/1937, Arts. 9 and 16; Dutch Wbk, Arts. 1a and 2–2b)
- **Confidentiality:** only authorised people may learn the reporter's identity. This includes indirect clues such as a unique shift or depot. (Directive Art. 16; Wbk Art. 1a)
- **GDPR:** collect the minimum needed (Art. 5(1)(c)). Health and other special-category data (Art. 9) and criminal-offence data (Art. 10) need extra restrictions. Use processor contracts for every vendor (Art. 28). Build data protection into the design (Art. 25).
- **Human decision:** investigation, closure, escalation and disclosure stay with a person. Drafting and routing may be automated. A decision with legal or similarly significant effect must not be made solely by automation (GDPR Art. 22(1)).

## How Čulo applies it
| Rule | Decision in this prototype |
|---|---|
| Identities (P1/P2) | Names, contact details and IDs are replaced or withheld on the employer's host before any model call. The identity mapping stays local and encrypted. |
| Sensitive content (P3) | Health data, trade-union membership and person-linked criminal allegations stay local. The report is held for a person. |
| Instructions in reports (P4) | Text that tries to steer the AI is quarantined locally. |
| Gateway (P5) | BRANE enforces the pinned team policy. Any unclean preview stops the request. |
| Human (P6) | The handler records every decision and reason. A failed model call never loses a report or restarts a clock. |

## Voice and ElevenLabs: no contradiction
The research concludes that **live caller audio must not go to ElevenLabs** in this MVP. ElevenLabs transcribes speech before BRANE can see it, and no legal basis exists for sending a real, unfiltered voice to that provider. The prototype follows this conclusion:
- The public entry point uses Version B of the [voice disclosure](voice-disclosure.md), a privacy-first local screen or clip. Capture and streaming are disabled, and live caller audio never reaches ElevenLabs.
- The ElevenLabs call shown in our evidence used **generated audio** (macOS `say`) with a fictional script. No real person spoke.
- ElevenLabs keeps transcripts for up to one day when a custom LLM is used, because it refuses zero retention in that setup. That retention is the open **product gap** that blocks any live use. It is not something we accept for real callers.

## Open before any real deployment
Executed processor agreements and transfer checks for every provider. A DPIA. An independent alternate handler. A safe return channel to the reporter. Retention and deletion tested across logs and backups. See the risk register in the [full research](legal-research.md#g-risk-register).
