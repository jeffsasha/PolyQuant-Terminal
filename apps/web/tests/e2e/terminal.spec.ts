import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';

test('local English terminal authenticates and keeps unsafe trading blocked',async({page})=>{
  const password=readFileSync(resolve(__dirname,'../../../../.local/login-password.txt'),'utf8').trim();
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Your research desk.'})).toBeVisible();
  await page.getByLabel('Local password').fill(password);
  await page.getByRole('button',{name:'Open terminal'}).click();
  await expect(page.getByTestId('paper-mode')).toHaveText('PAPER');
  await expect(page.getByText('Reference validation failed',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Enable live trading'})).toHaveCount(0);
  await page.getByRole('button',{name:'Data health',exact:true}).click();
  await expect(page.getByText('Reference reconciliation', {exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Switch theme'}).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme','light');
  await page.getByRole('button',{name:'Switch theme'}).click();
  await page.getByRole('button',{name:'Emergency stop'}).click();
  await expect(page.getByTestId('risk-state')).toContainText('HALTED');
  await page.reload();
  await expect(page.getByTestId('risk-state')).toContainText('HALTED');
  await page.getByRole('button',{name:'Resume paper account'}).click();
  await expect(page.getByTestId('risk-state')).toContainText('REFERENCE BLOCKED');
  await page.screenshot({path:resolve(__dirname,'../../../../docs/images/local-terminal.png'),fullPage:true});
});
