// Operator script for production verification: open the local website, sign in, press RUN (or STOP) on the
// selected bot profile and save a screenshot. Reads the generated local password file directly; never prints it.
// Usage: node press-run.mjs RUN|STOP [book_aggressive|book_experiment] [screenshot.png]
import {chromium} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..');
const [action = 'RUN', profile = 'book_aggressive', shot = resolve(root, '.local/verification-' + Date.now() + '.png')] =
  process.argv.slice(2);
const browser = await chromium.launch();
const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
await page.goto('http://127.0.0.1:3000/');
await page.getByLabel('Local password').fill(readFileSync(resolve(root, '.local/login-password.txt'), 'utf8').trim());
await page.getByRole('button', {name: 'Open terminal'}).click();
await page.getByTestId('bot-panel').waitFor();
if (action === 'RUN') {
  await page.getByLabel('Bot profile').selectOption(profile);
  await page.getByRole('button', {name: 'RUN', exact: true}).click();
} else {
  await page.getByRole('button', {name: 'STOP', exact: true}).click();
}
// Wait for the badge to reflect the command (the page refreshes state after the API call returns).
const want = action === 'RUN' ? /RUNNING|HALTED/ : /STOPPED/;
for (let i = 0; i < 40 && !want.test((await page.getByTestId('bot-status').textContent()) ?? ''); i++) {
  await page.waitForTimeout(250);
}
const status = await page.getByTestId('bot-status').textContent();
const notice = await page.getByRole('status').textContent().catch(() => '');
await page.screenshot({path: shot, fullPage: false});
console.log(JSON.stringify({action, profile, status, notice, screenshot: shot}));
await browser.close();
