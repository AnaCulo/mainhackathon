const local = new Intl.DateTimeFormat('en-CA', {timeZone:'Europe/Amsterdam', year:'numeric', month:'2-digit', day:'2-digit'});
export const localDay = value => local.format(new Date(value));
const day = date => date.toISOString().slice(0,10);
const at = value => new Date(value+'T12:00:00Z');
export function plusDays(value, n) {
  const date = at(value);
  date.setUTCDate(date.getUTCDate()+n);
  return day(date);
}
export function plusMonths(value, n) {
  const date = at(value);
  const last = new Date(Date.UTC(date.getUTCFullYear(),date.getUTCMonth()+n+1,0));
  last.setUTCDate(Math.min(last.getUTCDate(),date.getUTCDate()));
  return day(last);
}
// Conservative operational calendar. No extension is ever applied.
const holidays = new Set(('2026-01-01 2026-04-03 2026-04-05 2026-04-06 2026-04-27 2026-05-05 2026-05-14 2026-05-24 2026-05-25 2026-12-25 2026-12-26 '+
 '2027-01-01 2027-03-26 2027-03-28 2027-03-29 2027-04-27 2027-05-05 2027-05-06 2027-05-16 2027-05-17 2027-12-25 2027-12-26').split(' '));
export function target(date) {
  while ([0,6].includes(at(date).getUTCDay()) || holidays.has(date)) date=plusDays(date,-1);
  return date;
}
export function clocks(received, ack, feedback, now) {
  const today=localDay(now), ackDue=plusDays(localDay(received),7);
  const fallback=plusMonths(ackDue,3);
  const feedbackDue=ack ? plusMonths(localDay(ack),3) : fallback;
  return {ackDue,ackTarget:target(ackDue),fallback,feedbackDue,feedbackTarget:target(feedbackDue),
    calendarReview:![ackDue,feedbackDue].every(d=>/^(2026|2027)-/.test(d)),
    ackMissed:(ack ? localDay(ack) : today)>ackDue, feedbackMissed:(feedback ? localDay(feedback) : today)>feedbackDue};
}
