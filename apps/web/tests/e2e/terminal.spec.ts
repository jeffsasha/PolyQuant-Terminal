import {test,expect,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
async function login(page:Page){await page.goto('/');await page.getByLabel('Local password').fill(readFileSync(resolve(__dirname,'../../../../.local/login-password.txt'),'utf8').trim());await page.getByRole('button',{name:'Open terminal'}).click();await expect(page.getByTestId('paper-mode')).toHaveText('PAPER');}

test('English controls, persistent stop and strategy gate work',async({page})=>{
 await login(page);await expect(page.getByText('Reference reconstruction unresolved',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Enable live trading'})).toHaveCount(0);
 await page.getByRole('button',{name:'Emergency stop'}).click();await expect(page.getByTestId('risk-state')).toContainText('HALTED');
 await page.reload();await expect(page.getByTestId('risk-state')).toContainText('HALTED');
 await page.getByRole('button',{name:'Resume paper account'}).click();await expect(page.getByTestId('risk-state')).toContainText('MANUAL PAPER READY');
 await page.getByLabel('Paper account').selectOption('probability');await expect(page.getByTestId('risk-state')).not.toContainText('MANUAL PAPER READY');
 await page.getByRole('button',{name:'Data health',exact:true}).click();await expect(page.getByText('Reference reconciliation',{exact:true})).toBeVisible();
 await page.getByLabel('Paper account').selectOption('manual');
 await page.getByRole('button',{name:'Pause paper account'}).click();await expect(page.getByTestId('risk-state')).toContainText('HALTED');await page.getByRole('button',{name:'Resume paper account'}).click();
 await page.getByRole('button',{name:'Switch theme'}).click();await expect(page.locator('html')).toHaveAttribute('data-theme','light');await page.getByRole('button',{name:'Switch theme'}).click();
});

test('production 15m and 1h books support actual paper buys and exits',async({page})=>{
 test.setTimeout(180000);const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await login(page);
 await expect(page.getByTestId('contract-1h').getByRole('button',{name:/BTC UP/})).toBeEnabled({timeout:30000});
 const before=await (await page.request.get('/api/state')).json();const beforeFills=before.performance.manual.fill_count;
 for(const cadence of ['1h','15m']){
  const response=await page.request.get('/api/state');const state=await response.json();
  const market=state.markets.find((m:{horizon:string;end:string;start:string})=>m.horizon===cadence&&new Date(m.start).getTime()<=Date.now()&&new Date(m.end).getTime()-Date.now()>(cadence==='1h'?300000:120000));
  expect(market,`An open ${cadence} instrument with entry time is required for this production check`).toBeTruthy();
  const direction=Number(market.book?.asks[0]?.[0]??1)<.85?'UP':'DOWN';
  await page.getByTestId('contract-'+cadence).getByRole('button',{name:new RegExp('^'+direction+' ')}).click();
  await page.getByLabel('Contracts',{exact:true}).fill('1');await page.getByLabel('Limit (USD)',{exact:true}).fill('0.95');
  await page.getByLabel('Execution scenario').selectOption('conservative');
  await page.getByRole('button',{name:'Inspect costs & risk →'}).click();await expect(page.getByText('PAPER ELIGIBLE',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Place paper order',exact:true}).click();
  const buyId=(await page.getByTestId('submitted-order').innerText()).replace('Order ID: ','');
  await expect.poll(async()=> (await (await page.request.get('/api/paper/orders/'+buyId)).json()).status,{timeout:20000}).toBe('FILLED');
  const current=await (await page.request.get('/api/state')).json();const position=current.accounts.find((a:{id:string})=>a.id==='manual').positions.find((p:{market_id:string})=>p.market_id===market.id);
  expect(position.qty).toBe('1.00000000');
  await page.getByRole('button',{name:/^Positions/}).click();await page.getByTestId('record-'+position.id).getByRole('button',{name:'Prepare exit'}).click();
  await page.getByLabel('Limit (USD)',{exact:true}).fill('0.01');await page.getByRole('button',{name:'Inspect costs & risk →'}).click();await expect(page.getByText('PAPER ELIGIBLE',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Place paper order',exact:true}).click();
  const sellId=(await page.getByTestId('submitted-order').innerText()).replace('Order ID: ','');expect(sellId).not.toBe(buyId);
  await expect.poll(async()=> (await (await page.request.get('/api/paper/orders/'+sellId)).json()).status,{timeout:20000}).toBe('FILLED');
  await expect(page.getByTestId('record-'+sellId)).toBeVisible();await page.getByTestId('record-'+sellId).getByRole('button',{name:'Inspect order'}).click();await expect(page.getByRole('dialog')).toContainText('book_version');await page.getByRole('button',{name:'Close details'}).click();
 }
 await page.getByRole('button',{name:'Fills',exact:true}).click();await expect(page.getByRole('columnheader',{name:'fee',exact:true})).toBeVisible();
 await page.reload();await page.getByRole('button',{name:'Fills',exact:true}).click();await expect.poll(async()=> (await (await page.request.get('/api/state')).json()).performance.manual.fill_count).toBe(beforeFills+4);
 for(const name of ['Overview','Research','Recordings','Data health','Smart Money']){await page.getByRole('button',{name,exact:true}).click();}
 await page.getByRole('button',{name:'Recordings',exact:true}).click();await page.getByRole('button',{name:'Seal current recording'}).click();await page.getByRole('button',{name:'Verify recording'}).first().click();await expect(page.getByRole('dialog')).toBeVisible();await page.getByRole('button',{name:'Close details'}).click();
 await page.getByRole('button',{name:'Overview',exact:true}).click();await expect(page.locator('.chart-caption')).toContainText(/Latest candle: \d{2}:\d{2} UTC/);
 await page.screenshot({path:resolve(__dirname,'../../../../docs/images/production-paper-trading.png'),fullPage:true,animations:'disabled'});
 await page.getByRole('button',{name:'Switch theme'}).click();await expect(page.locator('html')).toHaveAttribute('data-theme','light');
 await page.setViewportSize({width:390,height:844});await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);expect(errors).toEqual([]);
});
