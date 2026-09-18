import type { ProjectView } from '../../projects/types'

const proxyLabel = (mode: string) => ({ sourceDefault: '跟随浏览器配置', none: '不使用代理', fixed: '固定代理', pool: '代理池' }[mode] ?? mode)

export function ProjectDefaultsPanel({ project, readOnly }: { project: ProjectView; readOnly: boolean }) {
  const resources = project.defaultResources
  return <section aria-label="项目默认资源" className="grid gap-4">
    <p className="m-0 text-sm text-muted">这里只展示当前项目默认资源。保存默认值请在项目资料中编辑；不会创建环境或启动任务。</p>
    <dl className="grid gap-4 sm:grid-cols-3">
      <div><dt className="text-xs font-medium text-muted">默认浏览器配置</dt><dd className="m-0 mt-1 text-sm">{resources.profileId ? '已指定浏览器配置' : '未指定'}</dd></div>
      <div><dt className="text-xs font-medium text-muted">默认代理</dt><dd className="m-0 mt-1 text-sm">{proxyLabel(resources.proxy.mode)}</dd></div>
      <div><dt className="text-xs font-medium text-muted">默认模型提供方</dt><dd className="m-0 mt-1 text-sm">{resources.modelProviderId ? '已指定模型提供方' : '未指定'}</dd></div>
    </dl>
    {readOnly ? <p className="m-0 text-sm text-muted">当前项目不可编辑。</p> : null}
  </section>
}
