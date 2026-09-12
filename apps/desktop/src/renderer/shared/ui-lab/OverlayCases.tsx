import { useState } from 'react'
import { Button } from '../components/ui/button'
import { Modal } from '../components/Modal'
import { Drawer } from '../components/Drawer'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../components/ui/dropdown-menu'
export function OverlayCases(){
 const [drawer,setDrawer]=useState(false),[dialog,setDialog]=useState(false)
 return <section aria-labelledby="overlays-title" className="grid gap-4 rounded-card border border-line bg-surface p-6"><h2 id="overlays-title" className="font-semibold">浮层、菜单与提示</h2><div className="flex gap-3"><Button onClick={()=>setDrawer(true)}>打开抽屉验收</Button><TooltipProvider><Tooltip><TooltipTrigger asChild><Button aria-label="字段帮助">帮助</Button></TooltipTrigger><TooltipContent>键盘聚焦立即显示，Escape关闭。</TooltipContent></Tooltip></TooltipProvider></div>
 <Drawer open={drawer} onOpenChange={setDrawer} title="抽屉验收" footer={<Button onClick={()=>setDrawer(false)}>完成验收</Button>}><DropdownMenu><DropdownMenuTrigger asChild><Button>抽屉中的操作</Button></DropdownMenuTrigger><DropdownMenuContent><DropdownMenuItem onSelect={()=>setDialog(true)}>编辑详情</DropdownMenuItem><DropdownMenuItem disabled>不可用操作</DropdownMenuItem></DropdownMenuContent></DropdownMenu><div className="h-96"/><p>滚动体底部</p><Modal open={dialog} onOpenChange={setDialog} title="菜单打开的弹窗"><Button onClick={()=>setDialog(false)}>返回抽屉</Button></Modal></Drawer></section>
}
