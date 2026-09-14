import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { main } from './qa-project-alignment-r1.mjs'

export const run = (options={}) => main({...options,recordPages:true})

if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href)run().catch(error=>{console.error(error);process.exitCode=1})
