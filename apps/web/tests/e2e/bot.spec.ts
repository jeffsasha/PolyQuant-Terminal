import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
test('RUN and STOP control the isolated experimental bot without manual tickets',async({page})=>{
 await page.goto('/');await page.getByLabel('Local password').fill(readFileSync(resolve(__dirname,'../../../../.local/login-password.txt'),'utf8').trim());await page.getByRole('button',{name:'Open terminal'}).click();
 await expect(page.getByLabel('Paper account')).toHaveValue('book_aggressive');
 await expect(page.getByTestId('bot-panel')).toContainText('UNVALIDATED EXPERIMENT');
 await expect(page.getByTestId('bot-panel')).toContainText('70% target / 80% entry cap');
 await expect(page.getByTestId('risk-per-trade')).toContainText('40%');
 await expect(page.getByRole('button',{name:'Place paper order',exact:true})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Inspect costs & risk →'})).toHaveCount(0);
 const before=await (await page.request.get('/api/state')).json();
 const locked=before.accounts.find((a:{id:string})=>a.id==='book_aggressive').halts.includes('DAILY_LOSS_LIMIT');
 if(locked){
  // A same-risk-day daily-loss lock must not be cleared by RUN, and the page must say why and until when.
  await expect(page.getByTestId('daily-lock')).toContainText('RUN cannot clear it');
  await page.getByRole('button',{name:'RUN',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Daily loss lock cannot be cleared');
  await expect(page.getByTestId('bot-status')).toHaveText('STOPPED');
 }else{
  await page.getByRole('button',{name:'RUN',exact:true}).click();await expect(page.getByTestId('bot-status')).toHaveText('RUNNING');
  await page.getByRole('button',{name:'STOP',exact:true}).click();await expect(page.getByTestId('bot-status')).toHaveText('STOPPED');
 }
 await page.reload();await expect(page.getByTestId('bot-status')).toHaveText('STOPPED');
 await page.getByLabel('Bot profile').selectOption('book_experiment');await expect(page.getByTestId('risk-per-trade')).toContainText('0.5%');
 await page.getByLabel('Bot profile').selectOption('book_aggressive');
 await page.getByRole('button',{name:'Smart Money',exact:true}).click();await expect(page.getByText('US copy trading unavailable',{exact:true})).toBeVisible();
 const state=await (await page.request.get('/api/state')).json();expect(state.mode).toBe('PAPER');expect(state.reference_validated).toBe(false);expect(state.copy_trading.enabled).toBe(false);
 await page.setViewportSize({width:390,height:844});await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
