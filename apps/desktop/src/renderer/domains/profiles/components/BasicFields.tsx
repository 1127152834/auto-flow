import { useFormContext } from 'react-hook-form'
import { FormField } from '../../../shared/components/FormField'
import { Input } from '../../../shared/components/ui/input'
import type { ProfileFormValues } from '../form-schema'

export function BasicFields() {
  const { register, formState: { errors } } = useFormContext<ProfileFormValues>()
  return <section aria-labelledby="profile-basic-fields" className="grid gap-5">
    <div>
      <h2 id="profile-basic-fields" className="m-0 text-lg font-semibold text-ink">基础信息</h2>
      <p className="mb-0 mt-1 text-sm text-muted">名称用于识别配置；指纹种子由 AutoFlow 维护。</p>
    </div>
    <div className="grid gap-4 sm:grid-cols-2">
      <FormField label="名称" htmlFor="profile-name" error={errors.name?.message}>{(a11y) => <>
        <Input {...a11y} {...register('name')} autoComplete="off" />
      </>}</FormField>
      <FormField label="描述" htmlFor="profile-description">{(a11y) => <>
        <Input {...a11y} {...register('description')} placeholder="可选，例如长期登录环境" />
      </>}</FormField>
    </div>
    <FormField label="起始网址" htmlFor="profile-start-url" error={errors.startUrl?.message} hint="支持 HTTP、HTTPS 或 about:blank。">{(a11y) => <>
      <Input {...a11y} {...register('startUrl')} inputMode="url" />
    </>}</FormField>
  </section>
}
