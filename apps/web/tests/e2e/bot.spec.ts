import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
test('RUN and STOP control the isolated experimental bot without manual tickets',async({page})=>{
 await page.goto('/');await page.getByLabel('Local password').fill(readFileSync(resolve(__dirname,'../../../../.local/login-password.txt'),'utf8').trim());await page.getByRole('button',{name:'Open terminal'}).click();
 await expect(page.getByLabel('Paper account')).toHaveValue('book_experiment');
 await expect(page.getByTestId('bot-panel')).toContainText('UNVALIDATED EXPERIMENT');
 await expect(page.getByRole('button',{name:'Place paper order',exact:true})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Inspect costs & risk →'})).toHaveCount(0);
 await page.getByRole('button',{name:'RUN',exact:true}).click();await expect(page.getByTestId('bot-status')).toHaveText('RUNNING');
 await page.getByRole('button',{name:'STOP',exact:true}).click();await expect(page.getByTestId('bot-status')).toHaveText('STOPPED');
 await page.reload();await expect(page.getByTestId('bot-status')).toHaveText('STOPPED');
 await page.getByRole('button',{name:'Smart Money',exact:true}).click();await expect(page.getByText('US copy trading unavailable',{exact:true})).toBeVisible();
 const state=await (await page.request.get('/api/state')).json();expect(state.mode).toBe('PAPER');expect(state.reference_validated).toBe(false);expect(state.copy_trading.enabled).toBe(false);
 await page.setViewportSize({width:390,height:844});await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
