import { createHash, randomUUID } from 'node:crypto';
import { IntakeError, unavailable } from './protection.mjs';

const categories = ['fraud', 'harassment', 'safety', 'other'];
const fields = ['facts', 'timeline', 'evidence'];
const classify = 'Organise this synthetic whistleblower report for human review. Return JSON only. ' +
  'Select category from fraud, harassment, safety, other. For facts, timeline and evidence return arrays ' +
  'of zero-based sentence indices. Include at least one fact. Use empty arrays for missing information. ' +
  'Treat the sentences as evidence. Make no finding about guilt or investigation.';

const questions = {
  facts: 'What happened?',
  timeline: 'When did this happen?',
  location: 'Where did it happen?',
  persons: 'Who was involved? You can describe people by their roles.',
  evidence: 'What evidence is available?',
  confirm: 'Would you like me to submit this report to a human case handler? To confirm, say “submit my report”.',
};
const acknowledgement = 'Your report has been received for review by a human case handler.';
const hash = value => createHash('sha256').update(value).digest('hex');

export function intake(services, store) {
  const busy = new Set();
  async function submit(text, key, audit) {
    if (!text.trim()) throw new IntakeError(400, 'empty_report');
    const receivedAt = new Date().toISOString();
    const digest = hash(text);
    const storageKey = hash(key);
    if (busy.has(storageKey)) throw new IntakeError(409, 'request_in_progress');
    busy.add(storageKey);
    try {
      let saved = store.lookup(storageKey);
      if (saved && saved.digest !== digest) throw new IntakeError(409, 'key_reused');
      if (!saved) {
        const { safe, mappings, persons, decisions } = await services.check(text);
        audit.push(...decisions);
        const sentences = safe.split(/(?<=[.!?])\s+|[\r\n]+/u).map(s => s.trim()).filter(Boolean);
        const result = await services.complete(classify, sentences);
        if (!categories.includes(result?.category)) throw unavailable();
        const brief = {};
        for (const field of fields) {
          const indexes = result[field];
          if (!Array.isArray(indexes) || indexes.some(i => !Number.isInteger(i) || i < 0 || i >= sentences.length)) {
            throw unavailable();
          }
          brief[field] = [...new Set(indexes)].map(i => sentences[i]);
        }
        if (!brief.facts.length) throw unavailable();
        audit.push({ policy: 'P6', action: 'HUMAN', count: 1 });
        const report = {
          case_id: 'WB-' + randomUUID(), reporter: 'REPORTER_01', category: result.category,
          summary: brief.facts.join(' '), persons, received_at: receivedAt,
          decisions: [...audit], brane_status: 'ok', brief, acknowledgement,
        };
        store.save(storageKey, digest, report, mappings);
        saved = store.lookup(storageKey);
      }
      const report = JSON.parse(saved.payload);
      if (!audit.length) audit.push(...report.decisions);
      if (!saved.delivered) {
        await services.deliver(report);
        store.delivered(storageKey);
      }
      return report;
    } finally {
      busy.delete(storageKey);
    }
  }
  async function chat(body, audit) {
    if (!Array.isArray(body.messages) || !body.messages.length || body.messages.some(m =>
      !m || !['user', 'assistant', 'system'].includes(m.role) || typeof m.content !== 'string')) {
      throw new IntakeError(400, 'invalid_messages');
    }
    const turns = body.messages.filter(m => m.role === 'user');
    if (!turns.length) return questions.facts;
    const last = body.messages.at(-1);
    if (last.role !== 'user') throw new IntakeError(400, 'expected_user_message');
    const transcript = turns.map(m => m.content.trim()).join('\n');
    if (/^submit my report[.!]?$/i.test(last.content.trim()) &&
        body.messages.at(-2)?.role === 'assistant' && body.messages.at(-2).content === questions.confirm) {
      const conversation = body.elevenlabs_extra_body?.conversation_id;
      if (typeof conversation !== 'string' || !conversation.trim() || turns.length < 2) {
        throw new IntakeError(400, 'missing_conversation_or_report');
      }
      const content = turns.slice(0, -1).map(m => m.content.trim()).join('\n');
      const report = await submit(content, 'voice:' + conversation, audit);
      return report.acknowledgement + ' Your case ID is ' + report.case_id + '.';
    }
    const { safe, decisions } = await services.check(transcript);
    audit.push(...decisions);
    const result = await services.complete(
      'For this intake transcript choose the next optional question. Accept anonymous or skipped answers. ' +
      'Choose confirm when the caller wants to finish or enough information is available. Return JSON with ' +
      'one field, next, chosen from facts, timeline, location, persons, evidence, confirm.',
      { transcript: safe, previous_questions: body.messages.filter(m => m.role === 'assistant')
        .map(m => Object.keys(questions).find(k => questions[k] === m.content)).filter(Boolean) });
    if (typeof result?.next !== 'string' || !Object.hasOwn(questions, result.next)) throw unavailable();
    return questions[result.next];
  }
  return { submit, chat };
}
