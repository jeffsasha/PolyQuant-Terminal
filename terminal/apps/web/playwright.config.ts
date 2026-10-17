import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'tests/e2e',workers:1,use:{baseURL:'http://127.0.0.1:3000',headless:true,viewport:{width:1600,height:1100}},timeout:45000});
