// Input offsets are JavaScript UTF-16 indices into the exact submitted string.
export const policies = {
  P1: 'PROTECT',
  P2: 'PROTECT',
  P3: 'BLOCK',
  P4: 'BLOCK',
};

export class IntakeError extends Error {
  constructor(status, code, decisions = []) {
    super(code);
    Object.assign(this, { status, code, decisions });
  }
}

export function unavailable() {
  return new IntakeError(503, 'brane_unavailable', [{ policy: 'P5', action: 'BLOCK', count: 1 }]);
}

export function protect(text, review) {
  if (review?.complete !== true || !Array.isArray(review.findings) ||
      !Array.isArray(review.checked) || !Object.keys(policies).every(p => review.checked.includes(p))) {
    throw unavailable();
  }
  const findings = [...review.findings];
  for (const f of findings) {
    if (!f || !Object.hasOwn(policies, f.policy) || !Number.isInteger(f.start) ||
        !Number.isInteger(f.end) || f.start < 0 || f.end <= f.start || f.end > text.length) {
      throw unavailable();
    }
  }
  const decisions = [];
  for (const [policy, action] of Object.entries(policies)) {
    const count = findings.filter(f => f.policy === policy).length;
    if (count) decisions.push({ policy, action, count });
  }
  if (decisions.some(d => d.action === 'BLOCK')) {
    throw new IntakeError(422, 'blocked_by_policy', decisions);
  }
  findings.sort((a, b) => a.start - b.start);
  const mappings = [];
  const people = new Map();
  let safe = '';
  let cursor = 0;
  for (const f of findings) {
    if (f.start < cursor) throw unavailable();
    const identity = text.slice(f.start, f.end);
    let token = 'REPORTER_01';
    if (f.policy === 'P2') {
      const key = f.entity ?? identity.normalize('NFKC').toLowerCase();
      if (typeof key !== 'string' || !key.trim()) throw unavailable();
      if (!people.has(key)) people.set(key, 'PERSON_' + String(people.size + 1).padStart(2, '0'));
      token = people.get(key);
    }
    safe += text.slice(cursor, f.start) + token;
    mappings.push({ token, identity });
    cursor = f.end;
  }
  safe += text.slice(cursor);
  // Catch an incomplete check which marked only the first occurrence of a known identity.
  const unmasked = [];
  cursor = 0;
  for (const f of findings) {
    unmasked.push(text.slice(cursor, f.start).normalize('NFKC').toLowerCase());
    cursor = f.end;
  }
  unmasked.push(text.slice(cursor).normalize('NFKC').toLowerCase());
  if (mappings.some(m => unmasked.some(s => s.includes(m.identity.normalize('NFKC').toLowerCase())))) {
    throw unavailable();
  }
  decisions.push({ policy: 'P5', action: 'ALLOW', count: 1 });
  return { safe, mappings, persons: [...people.values()], decisions };
}
