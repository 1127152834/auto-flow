import { useFormContext } from 'react-hook-form'
import { FormField } from '../../../shared/components/FormField'
import { Textarea } from '../../../shared/components/ui/textarea'
import type { ProfileFormValues } from '../form-schema'

export function AdvancedFields() {
  const { register, formState: { errors } } = useFormContext<ProfileFormValues>()
  return <section aria-labelledby="profile-advanced-fields" className="grid gap-5">
    <div>
      <h2 id="profile-advanced-fields" className="m-0 text-lg font-semibold text-ink">高级选项</h2>
      <p className="mb-0 mt-1 text-sm text-muted">扩展目录与 Chromium 启动参数均为可选，每行填写一项。</p>
    </div>
    <details className="rounded-control border border-line bg-surface-subtle p-4 text-sm text-ink">
      <summary className="cursor-pointer font-medium">查看填写说明</summary>
      <div className="mt-3 grid gap-3 text-muted">
        <p className="m-0">扩展目录应是已解压的 Chromium 扩展绝对路径，目录内直接包含 <code>manifest.json</code>；不要填写 <code>.crx</code> 文件。</p>
        <p className="m-0">启动参数通常以 <code>--</code> 开头，例如 <code>--disable-notifications</code> 或 <code>--window-position=40,40</code>。</p>
        <p className="m-0"><strong className="text-ink">AutoFlow 已管理：</strong> --user-data-dir、--fingerprint、--remote-debugging-address、--remote-debugging-port、--proxy-server、--load-extension。</p>
      </div>
    </details>
    <FormField label="扩展目录（每行一个）" htmlFor="profile-extension-paths" hint="只填写已解压扩展的文件夹路径。">
      <Textarea rows={4} placeholder={'例如：\nD:\\AutoFlow\\extensions\\my-extension'} {...register('extensionPathsText')} />
    </FormField>
    <FormField label="高级参数（每行一个）" htmlFor="profile-expert-args" error={errors.expertArgsText?.message} hint="每一行会作为一个独立 Chromium 启动参数。">
      <Textarea rows={5} placeholder={'例如：\n--disable-notifications\n--window-position=40,40'} {...register('expertArgsText')} />
    </FormField>
  </section>
}
