import {createHash} from 'node:crypto';
export function reject(status=422) {throw Object.assign(new Error('Request rejected'),{status});}
const exact=(o,keys)=>o && typeof o==='object' && !Array.isArray(o) && Object.keys(o).every(k=>keys.includes(k));
const string=s=>typeof s==='string' && s.trim().length>0 && s.length<=16000;
const arr=(a,fn)=>Array.isArray(a) && a.length<=512 && a.every(fn);
export function validate(b,key,now) {
  if (!exact(b,['case_id','reporter','category','summary','persons','received_at','decisions','brane_status','acknowledgement','brief']) ||
      typeof b.case_id!=='string' || !/^[A-Za-z0-9_.:-]{1,128}$/.test(b.case_id) || b.case_id!==key ||
      b.brane_status!=='ok' || b.reporter!=='REPORTER_01' || !['fraud','harassment','safety','corruption','discrimination','other'].includes(b.category) ||
      !string(b.summary) || !arr(b.persons,p=>typeof p==='string' && /^PERSON_[0-9]{2,}$/.test(p)) ||
      new Set(b.persons).size!==b.persons.length || typeof b.received_at!=='string' ||
      !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z$/.test(b.received_at) ||
      !Number.isFinite(Date.parse(b.received_at)) || new Date(b.received_at).toISOString().slice(0,19)!==b.received_at.slice(0,19) ||
      Date.parse(b.received_at)>now+60000) reject();
  if (!arr(b.decisions,d=>exact(d,['policy','action','count']) && Object.hasOwn(d,'count'))) reject();
  const pythonWire=b.decisions.some(d=>d.policy==='P6' && d.action==='HUMAN_ONLY');
  const actions={P1:'PROTECT',P2:'PROTECT',P5:'ALLOW',P6:pythonWire?'HUMAN_ONLY':'HUMAN'};
  // Python also records that a financial detail stayed local, or that a
  // combination of identifying details was withheld, without an occurrence count.
  if (pythonWire) actions.P3='LOCAL_ONLY';
  const validCount=d=>{
    if (d.policy==='P3') return pythonWire && d.count===null;
    if (d.policy==='P1' && pythonWire && d.count===null) return true;
    if (['P5','P6'].includes(d.policy)) return d.count===(pythonWire?null:1);
    return Number.isSafeInteger(d.count) && d.count>0;
  };
  if (!b.decisions.every(d=>Object.hasOwn(actions,d.policy) && actions[d.policy]===d.action && validCount(d)) ||
      new Set(b.decisions.map(d=>d.policy)).size!==b.decisions.length ||
      !['P5','P6'].every(p=>b.decisions.some(d=>d.policy===p)) ||
      (b.decisions.find(d=>d.policy==='P2')?.count??0)<b.persons.length) reject();
  if ('acknowledgement' in b && b.acknowledgement!=='Your report has been received for review by a human case handler.') reject();
  if ('brief' in b && (!exact(b.brief,['facts','timeline','evidence']) || !['facts','timeline','evidence'].every(f=>arr(b.brief[f],string)) ||
      b.brief.facts.join(' ')!==b.summary)) reject();
  const brief=b.brief??{facts:[b.summary],timeline:[],evidence:[]};
  return {id:b.case_id, received:b.received_at, category:b.category, summary:b.summary,
    persons:b.persons, brief:{facts:brief.facts,timeline:brief.timeline,evidence:brief.evidence},
    decisions:b.decisions.map(({policy,action,count})=>({policy,action,count})).sort((a,b)=>a.policy.localeCompare(b.policy))};
}
export const digest=value=>createHash('sha256').update(value).digest('hex');
