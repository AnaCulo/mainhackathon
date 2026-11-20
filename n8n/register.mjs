import {DatabaseSync} from 'node:sqlite';
import {randomUUID} from 'node:crypto';
import {validate,digest,reject} from './contract.mjs';
import {clocks,localDay} from './calendar.mjs';

export class Register {
  constructor(path, {actor='handler', demo=false, now=Date.now, routes=[], reviewBase='http://127.0.0.1:8788', table=false}={}) {
    this.db=new DatabaseSync(path);
    Object.assign(this,{actor,demo,now,reviewBase,table});
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA busy_timeout=3000;
      CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, digest TEXT NOT NULL, payload TEXT NOT NULL, task TEXT UNIQUE, actor TEXT,
        accepted TEXT, demo INTEGER, decision TEXT, reason TEXT, decided TEXT, feedback TEXT, approved TEXT, clocks TEXT);
      CREATE TABLE IF NOT EXISTS effects(id TEXT, kind TEXT, state TEXT, channel TEXT, updated TEXT, PRIMARY KEY(id,kind));
      CREATE TABLE IF NOT EXISTS inbox(id TEXT, kind TEXT, destination TEXT, message TEXT, at TEXT, PRIMARY KEY(id,kind));
      CREATE TABLE IF NOT EXISTS routes(id TEXT PRIMARY KEY);
      CREATE TABLE IF NOT EXISTS history(id TEXT, kind TEXT, state TEXT, at TEXT, actor TEXT);`);
    for (const id of routes) this.db.prepare('INSERT OR IGNORE INTO routes VALUES(?)').run(id);
  }
  time(){return new Date(this.now()).toISOString();}
  tx(fn){
    this.db.exec('BEGIN IMMEDIATE');
    try {const result=fn();this.db.exec('COMMIT');return result;}
    catch(e){this.db.exec('ROLLBACK');throw e;}
  }
  add(id,kind,channel){
    this.db.prepare("INSERT OR IGNORE INTO effects VALUES(?,?,'pending',?,?)").run(id,kind,channel,this.time());
  }
  accept(body,key){
    const data=validate(body,key,this.now()), json=JSON.stringify(data);
    return this.tx(()=>{
      const prior=this.db.prepare('SELECT digest FROM cases WHERE id=?').get(data.id);
      if(prior){if(prior.digest!==digest(json)) reject(409);return 200;}
      this.db.prepare('INSERT INTO cases(id,digest,payload,task,actor,accepted,demo,clocks) VALUES(?,?,?,?,?,?,?,?)')
        .run(data.id,digest(json),json,randomUUID(),this.actor,this.time(),+this.demo,JSON.stringify(clocks(data.received,null,null,this.now())));
      this.add(data.id,'ack','local reporter inbox');
      this.add(data.id,'notify','designated email capture');
      if(this.table)this.add(data.id,'table','n8n Data Table');
      return 201;
    });
  }
  get(id){return this.db.prepare('SELECT * FROM cases WHERE id=?').get(id);}
  effects(id){return this.db.prepare('SELECT * FROM effects WHERE id=? ORDER BY kind').all(id);}
  mark(id,kind,state,actor='dispatcher'){
    this.db.prepare('UPDATE effects SET state=?,updated=? WHERE id=? AND kind=?').run(state,this.time(),id,kind);
    this.db.prepare('INSERT INTO history VALUES(?,?,?,?,?)').run(id,kind,state,this.time(),actor);
  }
  deadlines(c){
    const effects=this.effects(c.id);
    const sent=k=>effects.find(e=>e.kind===k && e.state==='sent')?.updated;
    const ack=sent('ack'),feedback=sent('feedback');
    const dates=clocks(JSON.parse(c.payload).received,ack,feedback,this.now());
    const prior=JSON.parse(c.clocks);
    dates.ackMissed ||= prior.ackMissed;
    dates.feedbackMissed ||= prior.feedbackMissed;
    this.db.prepare('UPDATE cases SET clocks=? WHERE id=?').run(JSON.stringify(dates),c.id);
    const today=localDay(this.now());
    const elapsed=this.now()-Date.parse(c.accepted);
    for(const [kind,done,target,minutes] of [['ack',ack,dates.ackTarget,1],['feedback',feedback,dates.feedbackTarget,2]]) {
      if(done)continue;
      if(today>=target)this.add(c.id,kind+'-reminder','designated email capture');
      if(c.demo && elapsed>=minutes*60000)this.add(c.id,kind+'-demo-reminder','designated email capture');
    }
  }
  tick(){
    for(const c of this.db.prepare('SELECT * FROM cases').all())this.tx(()=>this.deadlines(c));
    const pending=this.db.prepare("SELECT * FROM effects WHERE state='pending' AND kind!='table' ORDER BY rowid LIMIT 100").all();
    for(const e of pending){
      try {
        this.tx(()=>this.capture(e));
      } catch {
        this.tx(()=>{
          if(this.effects(e.id).some(x=>x.kind===e.kind && x.state==='pending'))this.mark(e.id,e.kind,'failed');
        });
      }
    }
  }
  capture(e){
    if(!this.effects(e.id).some(x=>x.kind===e.kind && x.state==='pending'))return;
    const c=this.get(e.id), reporter=['ack','feedback'].includes(e.kind);
    if(reporter && !this.db.prepare('SELECT id FROM routes WHERE id=?').get(e.id)){
      this.mark(e.id,e.kind,'unreachable');
      return;
    }
    const destination=reporter?'synthetic mailbox '+e.id:c.actor+'@example.invalid';
    let message='Case '+e.id+' · '+this.reviewBase+'/review/'+encodeURIComponent(e.id);
    if(e.kind==='ack')message='Report received. Reference '+e.id;
    if(e.kind==='feedback')message=c.feedback;
    // The synthetic delivery receipt and its outbox transition commit together.
    this.db.prepare('INSERT INTO inbox VALUES(?,?,?,?,?)').run(e.id,e.kind,destination,message,this.time());
    this.mark(e.id,e.kind,'sent');
    if(reporter)this.deadlines(c);
  }
  route(id){
    this.tx(()=>{
      if(!this.get(id))reject(404);
      this.db.prepare('INSERT OR IGNORE INTO routes VALUES(?)').run(id);
      for(const e of this.effects(id).filter(e=>e.state==='unreachable'))this.mark(id,e.kind,'pending','local dispatcher');
    });
  }
  approve(id,task,actor,action,reason,conflictFree){
    this.tx(()=>{
      const c=this.get(id);
      if(!c || c.task!==task || c.actor!==actor || !conflictFree)reject(403);
      if(typeof reason!=='string'|| !reason.trim() || reason.length>1500)reject();
      if(action==='feedback'){
        if(!c.decision || c.approved)reject(409);
        this.db.prepare('UPDATE cases SET feedback=?,approved=? WHERE id=?').run(reason.trim(),this.time(),id);
        this.add(id,'feedback','local reporter inbox');
      }else{
        if(c.decision)reject(409);
        if(!['investigate','close','escalate'].includes(action))reject();
        this.db.prepare('UPDATE cases SET decision=?,reason=?,decided=? WHERE id=?').run(action,reason.trim(),this.time(),id);
      }
      this.db.prepare('INSERT INTO history VALUES(?,?,?,?,?)').run(id,'approval',action,this.time(),actor);
    });
  }
  async mirror(send){
    // Claim before network I/O. A crash or ambiguous response requires reconciliation.
    const e=this.tx(()=>{
      const e=this.db.prepare("SELECT * FROM effects WHERE kind='table' AND state='pending' LIMIT 1").get();
      if(e)this.mark(e.id,'table','uncertain');
      return e;
    });
    if(!e)return;
    let state='uncertain';
    try{state=await send(e.id,this.get(e.id));}catch{/* request may have arrived */}
    this.tx(()=>this.mark(e.id,'table',state));
  }
  reconcile(id,kind,state){
    this.tx(()=>{
      const e=this.effects(id).find(e=>e.kind===kind);
      if(!e || !['failed','uncertain'].includes(e.state) || !['sent','pending'].includes(state))reject(409);
      if(kind!=='table' && state==='sent')reject(409);
      this.mark(id,kind,state,'local reconciliation');
    });
  }
}
