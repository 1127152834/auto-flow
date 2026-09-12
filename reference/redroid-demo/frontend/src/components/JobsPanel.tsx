import type { Job } from '../api';

const statusLabels = { queued: '排队中', running: '执行中', done: '完成', failed: '失败（见逐台结果）' };
export function JobsPanel({ jobs, restarted, error }: { jobs: Job[]; restarted: boolean; error: string }) {
  return <section className="panel"><h2>任务结果</h2><p>后台并发 2。同一设备操作互斥；任务记录保存在当前服务进程，重启后不续跑。</p>
    {restarted && <p className="warning" role="status">管理服务已重启，之前的任务记录已丢失。请重新核对实例状态；原任务不会自动恢复。</p>}
    {error && <p className="error" role="alert">无法刷新任务：{error}</p>}
    {jobs.length === 0 && <p className="empty">提交创建或设备操作后，逐台结果会出现在这里。</p>}
    <div className="job-list">{[...jobs].reverse().map(job => <article className="job" key={job.id}><div className="section-heading"><strong>{job.action}</strong><span className={`badge ${job.status === 'failed' ? 'fail' : job.status === 'done' ? 'pass' : 'unknown'}`}>{statusLabels[job.status]} · {job.done}/{job.total}</span></div><small className="muted">{job.id}</small>
      {job.results.map((result, index) => <div className="job-result" key={`${result.instance_id}-${index}`}><strong>{result.name || result.instance_id || '创建请求'}</strong><p className={result.status === 'error' ? 'error' : ''}>{result.status === 'success' ? '成功：' : '失败：'}{result.message}</p>{result.data && <details open={job.action === 'root_check'}><summary>实际检查输出 / 结果数据</summary><pre>{JSON.stringify(result.data, null, 2)}</pre></details>}</div>)}
    </article>)}</div>
  </section>;
}
