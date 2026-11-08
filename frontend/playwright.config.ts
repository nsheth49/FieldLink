import { defineConfig } from '@playwright/test'
export default defineConfig({testDir:'./e2e',use:{baseURL:'http://127.0.0.1:5173',viewport:{width:1366,height:768},headless:true,channel:process.env.FIELDLINK_BROWSER_CHANNEL||'msedge'},reporter:'list',timeout:60000})
