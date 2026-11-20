# Voice disclosure for whistleblower intake

**Person C handoff · 20 November 2026.** Use **Version B** for the hackathon entry point. Run any demonstration of Version A with generated fictional audio, fictional session details and a closed test harness. A teammate reading a fictional report into a real microphone still supplies a real person's voice.

## Version A — Recorded voice under verified conditions

Use this wording only for a service that actually offers the choices below. It assumes an approved **local entry page** that can play a prompt, present buttons and the full privacy notice, and keep the microphone disconnected until the person chooses. It also assumes **locally controlled recording** after choice, approved ElevenLabs live speech processing, a protected full written account available for review, and an authorised human oral route. A different architecture needs a matching disclosure.

**Opening, before any caller audio is captured or sent**

> Hello. I’m an AI assistant with a computer-generated voice. I can help you report something that happened at work. Please wait to share details until you’ve chosen how to report.
>
> If you choose recorded voice, we’ll send your voice to ElevenLabs to turn your words into text. ElevenLabs hears what you say before our system can remove names. We’ll record the conversation to document your report. Our system uses a protected version of the text to draft a case. An authorised human case handler reviews it and decides what happens next.
>
> You can report without giving your name. Your voice, connection details or the events you describe could still identify you. Access to the report is restricted. In some circumstances the law can require information to be shared.
>
> You can use secure text instead, or ask to speak to a person without recording. The privacy notice on this page explains who handles the information, how long it is kept and how to exercise your rights.
>
> To use ElevenLabs voice processing and agree to the recording, choose “Start recorded voice”. For text, choose “Report by text”. For an unrecorded conversation, choose “Speak to a person”.

**After affirmative selection and successful connection**

> Recording has started. Share only what you think is needed. You can leave out your name. What happened?

**Before finishing an oral report**

> An authorised case handler will review your report. You can check the written account, ask for corrections and sign it if you agree. If you’d like updates, you can choose a safe way to receive them.

**If the caller asks to stop recording**

> I’ll stop here. You can continue by text or ask to speak to a person without recording.

Stop capture and disconnect the provider immediately on that request. Play the last line locally. A request to stop concerns future capture. Refer requests about existing records to the controller.

## Version B — Privacy-first fallback

**Play locally or display before opening a microphone, dialling a provider or creating a provider session.**

> This is an AI reporting assistant with a computer-generated voice. Please don’t say your report aloud. Voice reporting is turned off because we haven’t verified how the voice service would handle the call. Choose “Report by text” to use the secure text channel.

For the hackathon, follow with:

> This is a demonstration. Please use only made-up names and events.

For an actual employer service, provide its verified human oral and meeting options alongside text. The fallback on its own cannot fulfil the complete Dutch reporting procedure.

## Wiring and stop conditions

| Event | Required behaviour |
|---|---|
| Entry page loads | Play a local clip or display accessible equivalent text. Disable capture, streaming, pre-buffering, third-party analytics and auto-connect. If entry is only available after connecting to ElevenLabs, disable that entry point and display Version B before dialling. |
| Recorded voice offered | First confirm controller identity and contact, DPO if applicable, purposes, bases, categories, recipients, transfers, retention criteria, rights and complaint route in the accessible privacy notice. Verify local recording, supported languages, withdrawal control, safe text/human alternatives and limited access. Check upstream carrier, ASR, synthesis, transcript, logging and subprocessor practices on the actual tenant. If any required fact or choice is missing, use B. |
| User chooses “Start recorded voice” | Register the affirmative choice locally with session reference, notice version and time. Then start capture and confirm recording. Silence, continuing the call, a preselected choice or a vague “OK” does not authorise recording. The choice is permission for the documented recording and voice path. The controller must already have assessed lawful bases and transfers. |
| Text, human route, refusal, ambiguous choice or timeout | Keep the microphone off. Route the explicit selection, repeat choices accessibly once if appropriate, otherwise stop. Never initiate a call to confirm refusal. Offer a meeting on request through the employer's procedure. |
| Anonymous mode | Ask for no name. Offer a verified anonymous return mailbox if supported, or explain that updates may be impossible without a safe return route. Never promise that voice, metadata or a narrative cannot identify someone. |
| Model, gateway, recording indicator or privacy control fails mid-session | Stop accepting speech and disconnect. Offer a local text or human handoff. Preserve lawful material already received and the original receipt time. Notify the designated handler through the protected workflow. Never send an unfiltered transcript to recover a failed summary. |
| Text route or human review is unavailable | Do not describe an unavailable route as secure or staffed. Keep live intake disabled. For the demonstration, show the synthetic fixture locally. For a real employer, publish a verified alternative channel and recipient. |

The scripts implement the [voice data processing decision](policy-matrix.md#voice-data-processing-decision). Prior agreement to recording, a lawful basis for processing, and approval for an external service are separate questions. The spoken introduction addresses interaction transparency. Provider-side marking of generated audio is a separate check. [Legal analysis and sources](legal-research.md)
