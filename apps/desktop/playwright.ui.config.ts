import {defineConfig} from '@playwright/test'
export default defineConfig({
 testDir:'./tests/ui', fullyParallel:false, workers:1, timeout:90_000,
 expect:{timeout:10_000}, reporter:[['list'],['json',{outputFile:'test-results/ui-results.json'}]],
 outputDir:'test-results/ui', use:{trace:'off'},
})
