import {expect,it} from 'vitest'
import {mcpFormTransport,parseMcpMapping} from '../lib/mcpConfigText'
it('preserves delimiters and empty values while ignoring blank lines',()=>{
 expect(parseMcpMapping(' KEY =a=b==\n\nEMPTY=\nCase=1\ncase=2\n','env')).toEqual({KEY:'a=b==',EMPTY:'',Case:'1',case:'2'})
 expect(parseMcpMapping('X-Url: https://fixture.invalid:8443/mcp\r\nX-Empty:','headers')).toEqual({'X-Url':'https://fixture.invalid:8443/mcp','X-Empty':''})
})
it.each([['env','A=1\nbad',2],['env','=missing',1],['env','A=1\nA=2',2],['headers','X-A:1\nx-a:2',2],['headers','Bad Name: value',1],['headers','bad',1],['env','A=\0',1]] as const)('rejects invalid %s mapping %# with line number', (kind,text,line)=>{
 expect(()=>parseMcpMapping(text,kind)).toThrow(new RegExp(`第 ${line} 行`))
})
it('treats prototype-like keys as literal data rather than object mutation',()=>{
 const result=parseMcpMapping('__proto__=value\nconstructor=text','env')
 expect(Object.hasOwn(result,'__proto__')).toBe(true)
 expect(result.__proto__).toBe('value')
 expect(Object.getPrototypeOf(result)).toBe(Object.prototype)
})
it.each([
 [{command:'node'},'stdio'],[{url:'https://fixture.invalid/sse'},'sse'],[{url:'https://fixture.invalid/mcp'},'http'],
 [{transport:'streamable_http'},'http'],[{transport:'streamable-http'},'http'],[{transport:'HTTP'},'http'],[{transport:'Streamable_HTTP'},'http'],[{transport:'sse',command:'node'},'sse'],[{},'stdio'],
] as const)('normalizes legacy transport case %#', (server,expected)=>expect(mcpFormTransport(server)).toBe(expected))
