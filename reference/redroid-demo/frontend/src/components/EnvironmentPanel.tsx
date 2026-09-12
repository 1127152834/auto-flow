import type { Environment } from '../api';

export function EnvironmentPanel({ environment, error, refreshing, onRefresh }: {
  environment: Environment | null; error: string; refreshing: boolean; onRefresh: () => void;
}) {
  return <section className="panel environment" aria-labelledby="environment-title">
    <div className="section-heading"><div><h2 id="environment-title">运行环境</h2><p>检查实际 Docker 宿主的内核、架构与镜像。</p></div>
      <button onClick={onRefresh} disabled={refreshing}>{refreshing ? '检查中…' : '重新检查'}</button></div>
    {error && <p role="alert" className="error">无法读取环境：{error}</p>}
    {!environment && !error && <p className="muted">正在连接管理服务…</p>}
    {environment && <><p className={`status-line ${environment.ready ? 'success' : 'warning'}`}>
      {environment.ready ? '环境检查通过，请选择兼容的已缓存镜像' : environment.docker_available ? 'Docker 已连接，宿主条件尚未满足' : 'Docker 不可用，当前不能管理实例'}
    </p><div className="checks">{environment.checks.map((check, index) => <div className="check" key={`${check.name}-${index}`}>
      <span className={`badge ${check.status}`}>{({ pass: '通过', fail: '未通过', unknown: '待验证' })[check.status]}</span><div><strong>{check.name}</strong><p>{check.message}</p></div>
    </div>)}</div><details><summary>镜像缓存与宿主信息</summary><ul>{environment.images.map(image => <li key={image.ref}><code>{image.ref}</code> · {image.cached ? '已缓存' : '未缓存'}{image.architecture && ` · ${image.architecture}`}{image.cached && image.compatible === false && <span className="error"> · 架构不匹配，无法创建</span>}{image.id && <small className="digest">{image.id}</small>}</li>)}</ul><pre>{JSON.stringify(environment.daemon, null, 2)}</pre></details></>}
  </section>;
}
