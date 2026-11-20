// Provision only the new, unclaimed disposable loopback instance.
import {randomBytes} from 'node:crypto';
import {readFileSync,writeFileSync,mkdtempSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
const origin='http://127.0.0.1:'+Number(process.env.DEMO_N8N_PORT??5689),token=()=>randomBytes(32).toString('hex');
const directory=mkdtempSync(join(tmpdir(),'culo-demo-')),file=join(directory,'demo.env');
const config={CASE_DIR:directory,N8N_ORIGIN:origin,N8N_TOKEN:token(),WORKER_TOKEN:token(),HANDLER_PASSWORD:token(),DEMO_CLOCK:'1',SYNTHETIC_MAILBOX_CASES:'WB-0007',HANDLER_REF:'handler',N8N_WEBHOOK_URL:origin+'/webhook/protected-case'};
config.DEMO_REGISTER_PORT=Number(process.env.DEMO_REGISTER_PORT??8788);
config.DEMO_INTAKE_PORT=Number(process.env.DEMO_INTAKE_PORT??8000);
let cookie='',key='';
async function call(path,method='GET',body){
  const headers={'content-type':'application/json'};
  if(path.startsWith('/rest/')&&cookie)headers.cookie=cookie;
  if(path.startsWith('/api/'))headers['X-N8N-API-KEY']=key;
  const res=await fetch(origin+path,{method,headers,body:JSON.stringify(body)});
  if(!res.ok)throw Error(method+' '+path+' returned '+res.status+' '+(await res.text()).replace(/[a-zA-Z0-9_.-]{30,}/g,'[redacted]').slice(0,350));
  cookie=res.headers.getSetCookie()[0]?.split(';')[0]??cookie;
  return res.json();
}
const settings=await call('/rest/settings');
if(settings.data.userManagement?.showSetupOnFirstLoad!==true)throw Error('Use a fresh, unclaimed disposable n8n profile');
await call('/rest/owner/setup','POST',{email:'owner@example.invalid',firstName:'Demo',lastName:'Owner',password:'Aa1!'+token().slice(0,36)});
writeFileSync(join(directory,'setup-session'),cookie,{mode:0o600});
const {data:scopes}=await call('/rest/api-keys/scopes');
const issue=async(label,scopes)=>(await call('/rest/api-keys','POST',{label,scopes,expiresAt:Math.floor(Date.now()/1000)+86400})).data.rawApiKey;
key=await issue('Demo setup',scopes.filter(s=>['credential:create','workflow:create','workflow:activate','workflow:publish','dataTable:create'].includes(s)));
const wf=JSON.parse(readFileSync(new URL('protected-case.json',import.meta.url)));
for(const node of wf.nodes){
  if(node.type==='n8n-nodes-base.httpRequest')
    node.parameters.url=node.parameters.url.replace('http://127.0.0.1:8788/', 'http://127.0.0.1:'+config.DEMO_REGISTER_PORT+'/');
}
for(const [name,value] of [['Protected intake',config.N8N_TOKEN],['Local dispatcher',config.WORKER_TOKEN]]){
  const cred=await call('/api/v1/credentials','POST',{name,type:'httpHeaderAuth',data:{name:'Authorization',value:'Bearer '+value}});
  for(const n of wf.nodes)if(n.credentials?.httpHeaderAuth.name===name)n.credentials.httpHeaderAuth.id=cred.id;
}
const table=await call('/api/v1/data-tables','POST',{name:'Protected case references',columns:['case_id','received_at'].map(name=>({name,type:'string'}))});
config.TABLE_ID=table.id;
config.TABLE_API_KEY=await issue('Case reference index',scopes.filter(s=>['dataTableRow:read','dataTableRow:create'].includes(s)));
const {name,nodes,connections,settings:workflowSettings}=wf;
const saved=await call('/api/v1/workflows','POST',{name,nodes,connections,settings:workflowSettings});
await call('/api/v1/workflows/'+saved.id+'/activate','POST',{});
writeFileSync(file,Object.entries(config).map(([k,v])=>k+'='+v).join('\n'),{mode:0o600,flag:'wx'});
console.log(file);

