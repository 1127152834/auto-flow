import '@testing-library/jest-dom/vitest'
import {cleanup,render,screen} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {afterEach,expect,it,vi} from 'vitest'
import {ProjectOverviewPage} from './ProjectOverviewPage'
import type {ProjectView} from '../types'
afterEach(cleanup)
const project={projectId:'p',name:'内容采集项目',description:'收集资料，整理内容，维护项目数据',lifecycleState:'active',updatedAt:'2026-09-13T00:00:00Z'} as ProjectView
it('keeps the original visible project context and a working breadcrumb return above the data card',async()=>{
 const back=vi.fn(),tabs=vi.fn();render(<ProjectOverviewPage project={project} tab="data" tableDetail tableName="资料库" disabled={false} onBack={back} onEdit={vi.fn()} onTabChange={tabs}><section aria-label="数据卡片"><h1>新增记录</h1></section></ProjectOverviewPage>)
 expect(screen.getByRole('navigation',{name:'当前位置'})).toHaveTextContent('项目 / 内容采集项目 / 数据 / 资料库');expect(screen.getByRole('heading',{level:2,name:'内容采集项目'})).toBeVisible();expect(screen.getByText(project.description)).toBeVisible();expect(screen.getAllByRole('heading',{level:1})).toHaveLength(1)
 await userEvent.click(screen.getByRole('button',{name:'返回项目目录'}));expect(back).toHaveBeenCalledOnce()
 await userEvent.click(screen.getByRole('button',{name:'概览'}));expect(tabs).toHaveBeenCalledWith('overview')
})
it('keeps project editing on the data directory but not the record frame',()=>{
 const options={project,tab:'data' as const,disabled:false,onBack:vi.fn(),onEdit:vi.fn(),onTabChange:vi.fn()};const v=render(<ProjectOverviewPage {...options}>数据目录</ProjectOverviewPage>);expect(screen.getByRole('button',{name:'编辑项目'})).toBeVisible()
 v.rerender(<ProjectOverviewPage {...options} tableDetail>记录页面</ProjectOverviewPage>);expect(screen.queryByRole('button',{name:'编辑项目'})).not.toBeInTheDocument()
})
