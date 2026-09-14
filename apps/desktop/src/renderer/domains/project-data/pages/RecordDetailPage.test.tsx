import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { RecordDetailPage } from './RecordDetailPage'
afterEach(cleanup)
it('keeps Gallery metadata in the status card and deletion behind more', async () => {
 const remove=vi.fn()
 render(<RecordDetailPage title="温室记录" recordKeyLabel="文本 · 001" updatedAt="2026-09-13T00:00:00Z" fieldsView={<p>业务值</p>} statusForm={<p>状态表单</p>} onBack={vi.fn()} onEdit={vi.fn()} onDelete={remove}/>)
 expect(screen.getByRole('heading',{level:2,name:'温室记录'})).toBeVisible()
 expect(screen.queryByRole('button',{name:'返回记录列表'})).not.toBeInTheDocument()
 expect(screen.queryByRole('button',{name:'删除记录'})).not.toBeInTheDocument()
 const status=screen.getByRole('region',{name:'业务状态'})
 expect(within(status).getByText('最近修改')).toBeVisible()
 expect(within(status).getByText('文本 · 001')).toBeVisible()
 expect(screen.queryByRole('region',{name:'时间信息'})).not.toBeInTheDocument()
 await userEvent.click(screen.getByRole('button',{name:'更多记录操作'}))
 await userEvent.click(screen.getByRole('menuitem',{name:'删除记录'}))
 expect(remove).toHaveBeenCalledOnce()
})
it.each(['readonly','disabled','loading'] as const)('blocks an already open deletion menu when %s changes',async flag=>{
 const remove=vi.fn(),props={title:'记录',fieldsView:<p>业务字段</p>,onBack:vi.fn(),onEdit:vi.fn(),onDelete:remove};
 const view=render(<RecordDetailPage {...props}/>);
 await userEvent.click(screen.getByRole('button',{name:'更多记录操作'}));
 view.rerender(<RecordDetailPage {...props} {...{[flag]:true}}/>);
 const item=screen.getByRole('menuitem',{name:'删除记录'});
 expect(item).toHaveAttribute('data-disabled');
 await userEvent.click(item);expect(remove).not.toHaveBeenCalled();
})
