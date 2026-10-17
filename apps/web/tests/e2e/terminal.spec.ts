import {test,expect,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
async function login(page:Page){await page.goto('/');await page.getByLabel('Local password').fill(readFileSync(resolve(__dirname,'../../../../.local/login-password.txt'),'utf8').trim());await page.getByRole('button',{name:'Open terminal'}).click();await expect(page.getByTestId('paper-mode')).toHaveText('PAPER');}

async function inspect(page:Page){
 for(let attempt=0;attempt<4;attempt++){
  const waiting=page.waitForResponse(response=>response.url().endsWith('/api/paper/preview'));
  await page.getByRole('button',{name:'Inspect costs & risk →'}).click();const result=await (await waiting).json();
  if(result.allowed)return;
  if(!result.reasons.some((reason:string)=>['BOOK_REFRESH_FAILED','VENUE_RATE_LIMITED','STALE_BOOK'].includes(reason)))throw new Error('Paper risk rejection: '+result.reasons.join(', '));
  await page.waitForTimeout(Math.max(1000,(result.retry_after||2)*1000));
 }
 throw new Error('Fresh production book remained unavailable after bounded retries');
}

test('English controls, persistent stop and strategy gate work',async({page})=>{
 await login(page);await expect(page.getByText('Reference reconstruction unresolved',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Enable live trading'})).toHaveCount(0);
 await page.getByRole('button',{name:'Emergency stop'}).click();await expect(page.getByTestId('risk-state')).toContainText('HALTED');
 await page.reload();await expect(page.getByTestId('risk-state')).toContainText('HALTED');
 await page.getByRole('button',{name:'Resume paper account'}).click();await expect(page.getByTestId('risk-state')).not.toContainText('HALTED');
 await page.getByLabel('Paper account').selectOption('probability');await expect(page.getByTestId('risk-state')).not.toContainText('MANUAL PAPER');
 await page.getByRole('button',{name:'Data health',exact:true}).click();await expect(page.getByText('Reference reconciliation',{exact:true})).toBeVisible();
 await page.getByLabel('Paper account').selectOption('manual');
 await page.getByRole('button',{name:'Pause paper account'}).click();await expect(page.getByTestId('risk-state')).toContainText('HALTED');await page.getByRole('button',{name:'Resume paper account'}).click();
 await page.getByRole('button',{name:'Switch theme'}).click();await expect(page.locator('html')).toHaveAttribute('data-theme','light');await page.getByRole('button',{name:'Switch theme'}).click();
});

test('production paper lifecycle resumes safely across fills, exits and official settlement',async({page})=>{
 test.setTimeout(240000);const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await login(page);await page.getByLabel('Paper account').selectOption('verification');
 for(const cadence of ['1h','15m']){
  let state=await (await page.request.get('/api/state')).json();
  let buy=state.orders.find((o:{account_id:string;horizon:string;side:string;status:string})=>o.account_id==='verification'&&o.horizon===cadence&&o.side.startsWith('BUY')&&o.status==='FILLED');
  if(!buy){
   const market=state.markets.find((m:{horizon:string;start:string;end:string})=>m.horizon===cadence&&new Date(m.start).getTime()<=Date.now()&&new Date(m.end).getTime()-Date.now()>(cadence==='1h'?300000:120000));expect(market).toBeTruthy();
   const direction=Number(market.book?.asks[0]?.[0]??1)<.85?'UP':'DOWN';
   await page.getByTestId('contract-'+cadence).getByRole('button',{name:new RegExp('^'+direction+' ')}).click();await page.getByLabel('Contracts',{exact:true}).fill('1');await page.getByLabel('Limit (USD)',{exact:true}).fill('0.95');
   await page.getByLabel('Execution scenario').selectOption('conservative');await inspect(page);await page.getByRole('button',{name:'Place paper order',exact:true}).click();
   const id=(await page.getByTestId('submitted-order').innerText()).replace('Order ID: ','');await expect.poll(async()=> (await (await page.request.get('/api/paper/orders/'+id)).json()).status,{timeout:25000}).toBe('FILLED');
   buy=await (await page.request.get('/api/paper/orders/'+id)).json();
  }
  expect(buy.book_version).toBeTruthy();
  state=await (await page.request.get('/api/state')).json();
  let position=state.accounts.find((a:{id:string})=>a.id==='verification').positions.find((p:{market_id:string})=>p.market_id===buy.market_id);
  if(position){
   const terms=state.markets.find((m:{id:string})=>m.id===buy.market_id);
   if(terms&&new Date(terms.end).getTime()>Date.now()){
    await page.getByRole('button',{name:/^Positions/}).click();await page.getByTestId('record-'+position.id).getByRole('button',{name:'Prepare exit'}).click();await page.getByLabel('Limit (USD)',{exact:true}).fill('0.01');
    for(let attempt=0;attempt<3;attempt++){
     await inspect(page);await page.getByRole('button',{name:'Place paper order',exact:true}).click();const id=(await page.getByTestId('submitted-order').innerText()).replace('Order ID: ','');
     await expect.poll(async()=> (await (await page.request.get('/api/paper/orders/'+id)).json()).status,{timeout:25000}).not.toBe('PENDING_ARRIVAL');
     const result=await (await page.request.get('/api/paper/orders/'+id)).json();if(result.status==='FILLED')break;
     expect(['ARRIVAL_BOOK_REFRESH_FAILED','ARRIVAL_REVALIDATION_FAILED','ARRIVAL_BOOK_NOT_OBSERVED']).toContain(result.reason);
    }
   }
   await expect.poll(async()=>{
    const s=await (await page.request.get('/api/state')).json();return s.position_history.find((p:{account_id:string;market_id:string;status:string})=>p.account_id==='verification'&&p.market_id===buy.market_id&&p.status!=='OPEN')?.status;
   },{timeout:120000}).toMatch(/CLOSED|SETTLED/);
  }
  const final=await (await page.request.get('/api/state')).json();
  const closed=final.position_history.find((p:{account_id:string;market_id:string;status:string})=>p.account_id==='verification'&&p.market_id===buy.market_id&&p.status!=='OPEN');expect(closed).toBeTruthy();
  if(closed.status==='SETTLED')expect(final.settlements.some((s:{market_id:string;payload:{final:boolean}})=>s.market_id===buy.market_id&&s.payload.final)).toBe(true);
 }
 await page.getByRole('button',{name:'Fills',exact:true}).click();await expect(page.getByRole('columnheader',{name:'fee',exact:true})).toBeVisible();await page.reload();await page.getByLabel('Paper account').selectOption('verification');await page.getByRole('button',{name:'Fills',exact:true}).click();await expect(page.locator('.table-scroll tbody tr').first()).toBeVisible();
 for(const name of ['Overview','Research','Recordings','Data health','Smart Money'])await page.getByRole('button',{name,exact:true}).click();
 await page.getByRole('button',{name:'Recordings',exact:true}).click();await page.getByRole('button',{name:'Seal current recording'}).click();await page.getByRole('button',{name:'Verify recording'}).first().click();await expect(page.getByRole('dialog')).toBeVisible();await page.getByRole('button',{name:'Close details'}).click();
 await page.getByRole('button',{name:'Positions',exact:false}).click();await page.screenshot({path:resolve(__dirname,'../../../../docs/images/production-paper-trading.png'),fullPage:true,animations:'disabled'});
 await page.getByRole('button',{name:'Switch theme'}).click();await expect(page.locator('html')).toHaveAttribute('data-theme','light');await page.setViewportSize({width:390,height:844});await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);expect(errors).toEqual([]);
});
