import { expect, it } from 'vitest'
import { evaluateJsScript } from '../lib/jsScript'
it('returns JSON results and deep copies variable inputs',()=>{
 const variables={list:[1],object:{value:1}}
 expect(evaluateJsScript('function main(vars){vars.list.push(2); vars.object.value=3; return {ok:true}}',variables)).toEqual({success:true,result:{ok:true},variables:{list:[1,2],object:{value:3}}})
 expect(variables).toEqual({list:[1],object:{value:1}})
})
it.each(['function main(){return undefined}', 'function main(){}'])('normalizes absent return to null: %s',code=>{
 expect(evaluateJsScript(code,{})).toEqual({success:true,result:null,variables:{}})
})
it.each(['return new Date()', 'return {[Symbol()]:1}', 'return Array(2)', 'return {toJSON(){return 1}}', 'return NaN','return Infinity','return 1n','return ()=>1','return {bad:undefined}','const a={};a.self=a;return a','vars.bad=undefined;return 1'])('rejects non-JSON output: %s',body=>{
 expect(evaluateJsScript(`function main(vars){${body}}`,{})).toMatchObject({success:false,error:expect.any(String)})
})
it.each(['async function main(){return 1}', 'function main(){return Promise.reject(new Error("failure"))}'])('rejects asynchronous main: %s',code=>{
 expect(evaluateJsScript(code,{})).toMatchObject({success:false,error:expect.stringContaining('不支持异步')})
})
it.each(['const x=1','function main( {','function main(){throw new Error("业务错误")}'])('returns explicit script failure: %s',code=>{
 expect(evaluateJsScript(code,{})).toMatchObject({success:false,error:expect.any(String)})
})
