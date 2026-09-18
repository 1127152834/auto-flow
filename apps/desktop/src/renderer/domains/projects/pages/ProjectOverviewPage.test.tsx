import '@testing-library/jest-dom/vitest'
import {cleanup,render,screen,within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {afterEach,expect,it,vi} from 'vitest'
import {ProjectOverviewPage} from './ProjectOverviewPage'
import type {ProjectOverview,ProjectView} from '../types'
afterEach(cleanup)
const project={projectId:'p',createdAt:'2026-09-01T00:00:00Z',name:'内容采集项目',description:'收集资料，整理内容，维护项目数据',lifecycleState:'active',updatedAt:'2026-09-13T00:00:00Z'} as ProjectView
it('keeps the original visible project context and a working breadcrumb return above the data card',async()=>{
 const back=vi.fn(),tabs=vi.fn();render(<ProjectOverviewPage project={project} tab="data" tableDetail tableName="资料库" disabled={false} onBack={back} onEdit={vi.fn()} onTabChange={tabs}><section aria-label="数据卡片"><h2>新增记录</h2></section></ProjectOverviewPage>)
 expect(screen.getByRole('navigation',{name:'当前位置'})).toHaveTextContent('项目 / 内容采集项目 / 数据 / 资料库');expect(screen.getByRole('heading',{level:1,name:'内容采集项目'})).toBeVisible();expect(screen.getByText(project.description)).toBeVisible();expect(screen.getAllByRole('heading',{level:1})).toHaveLength(1)
 await userEvent.click(screen.getByRole('button',{name:'返回项目目录'}));expect(back).toHaveBeenCalledOnce()
 await userEvent.click(screen.getByRole('button',{name:'概览'}));expect(tabs).toHaveBeenCalledWith('overview')
})
it('keeps project editing on the data directory but not the record frame',()=>{
 const options={project,tab:'data' as const,disabled:false,onBack:vi.fn(),onEdit:vi.fn(),onTabChange:vi.fn()};const v=render(<ProjectOverviewPage {...options}>数据目录</ProjectOverviewPage>);expect(screen.getByRole('button',{name:'编辑项目'})).toBeVisible()
 v.rerender(<ProjectOverviewPage {...options} tableDetail>记录页面</ProjectOverviewPage>);expect(screen.queryByRole('button',{name:'编辑项目'})).not.toBeInTheDocument()
})
it('uses the same title and return frame for automations and runs as the other tabs',()=>{
 const options={project,disabled:false,onBack:vi.fn(),onEdit:vi.fn(),onTabChange:vi.fn()}
 const view=render(<ProjectOverviewPage {...options} tab="data">数据目录</ProjectOverviewPage>)
 const mainClassName=screen.getByRole('main').className
 const navigationClassName=screen.getByRole('navigation',{name:'当前位置'}).className

 for(const tab of ['automations','runs'] as const){
  view.rerender(<ProjectOverviewPage {...options} tab={tab}>{tab}</ProjectOverviewPage>)
  expect(screen.getByRole('main')).toHaveClass(...mainClassName.split(' '))
  expect(screen.getByRole('navigation',{name:'当前位置'})).toHaveClass(...navigationClassName.split(' '))
 }
})
it('returns from the breadcrumb to the table directory without adding an in-card back row',async()=>{
 const back=vi.fn(),tableBack=vi.fn();render(<ProjectOverviewPage project={project} tab="data" tableDetail tableName="资料库" disabled={false} onBack={back} onTableBack={tableBack} onEdit={vi.fn()} onTabChange={vi.fn()}/>);
 await userEvent.click(screen.getByRole('button',{name:'返回数据表'}));expect(tableBack).toHaveBeenCalledOnce();expect(back).not.toHaveBeenCalled();await userEvent.click(screen.getByRole('button',{name:'返回项目目录'}));expect(back).toHaveBeenCalledOnce();
})

it('uses the record-list breadcrumb return for a record page while retaining the project link',async()=>{
 const back=vi.fn(),tableBack=vi.fn();render(<ProjectOverviewPage project={project} tab="data" tableDetail tableName="资料库" tableBackLabel="返回记录列表" disabled={false} onBack={back} onTableBack={tableBack} onEdit={vi.fn()} onTabChange={vi.fn()}/>);
 await userEvent.click(screen.getByRole('button',{name:'返回记录列表'}));expect(tableBack).toHaveBeenCalledOnce();expect(back).not.toHaveBeenCalled();expect(screen.queryByRole('button',{name:'返回数据表'})).not.toBeInTheDocument();
})
const overview={project,counts:{automations:2,tables:3,batches:1,environments:0},availability:{} as never,activity:[{kind:'task' as const,resource:{type:'task',projectId:'p',taskId:'t1'},severity:'error' as const,message:'运行失败',occurredAt:'2026-09-19T10:00:00Z'}],recent:[{activityId:'a1',kind:'batch',resource:{type:'batch',projectId:'p',batchId:'b1'},summary:'批次完成',occurredAt:'2026-09-19T10:00:00Z'}],dataChanges:{timezone:'Asia/Shanghai',dayStart:'2026-09-19T00:00:00+08:00',newRecords:1,updatedRecords:0}} as ProjectOverview
it('renders the recorded overview and routes a resource action into the workspace',async()=>{
 const open=vi.fn();render(<ProjectOverviewPage project={project} tab="overview" disabled={false} overview={overview} onOpenResource={open} onBack={vi.fn()} onEdit={vi.fn()} onTabChange={vi.fn()}/>)
 expect(screen.getByLabelText('项目计数')).toHaveTextContent('自动化');expect(screen.getByText('运行失败')).toBeVisible();expect(within(screen.getByRole('region',{name:'最近活动'})).getByText('批次完成')).toBeVisible();expect(screen.queryByRole('heading',{name:'项目资料'})).not.toBeInTheDocument()
 await userEvent.click(screen.getByRole('button',{name:'打开'}));expect(open).toHaveBeenCalledWith({tab:'runs',batchId:'b1'})
})
it('keeps the last overview on screen when a refresh fails',()=>{
 render(<ProjectOverviewPage project={project} tab="overview" disabled={false} overview={overview} overviewError="网络错误" onBack={vi.fn()} onEdit={vi.fn()} onTabChange={vi.fn()}/>)
 expect(screen.getByRole('status')).toHaveTextContent('概览刷新失败：网络错误');expect(screen.getByLabelText('项目计数')).toBeVisible()
})
it('keeps the project facts card while the overview has not loaded yet',()=>{
 render(<ProjectOverviewPage project={project} tab="overview" disabled={false} onBack={vi.fn()} onEdit={vi.fn()} onTabChange={vi.fn()}/>)
 expect(screen.getByRole('heading',{name:'项目资料'})).toBeVisible()
})
