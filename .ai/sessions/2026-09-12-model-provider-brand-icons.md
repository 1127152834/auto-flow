# 模型供应商品牌图标修正

- 日期：2026-09-12
- 状态：confirmed；独立分支实现与检查完成，已同步baseline并在当前Electron验证。
- 来源：用户指出模型管理图标不真实；实际 Electron 供应商选择弹窗截图、官方品牌/媒体包、官网 favicon、官方 GitHub 与 LobeHub 图形对照。
- 范围：模型供应商图标与共享展示组件；保持预设 ID、协议、连接地址和原交互。
- 实施：`codex/model-provider-brand-icons` 独立worktree；10个本地品牌文件，8个直接官方文件、2个LobeHub MIT整理版。OpenAI由错误书本换成Blossom，Qwen不再使用阿里云标志，智谱不再使用通用连接符；保留原品牌颜色并移除人为彩底。
- 组件：ProviderLogo统一三种尺寸，OpenAI/SiliconFlow利用原SVG留白；自定义使用通用符号。图标加载失败仅影响该source，切换供应商可恢复。
- 验证：模型模块5个测试文件/39项通过，TypeScript、ESLint、生产构建通过；SVG/PNG格式及脚本/外链检查通过；独立只读复核无问题。
- 证据：`docs/migration/model-brand-icons/`；完整来源、SHA256和许可记录位于`renderer/domains/models/assets/brands/README.md`。

- 落地：在独立分支接入同期已提交的浏览器/代理变化后再次通过39项模型测试、type/lint/build；baseline快进到994a73f。原检出6个未提交文件SHA256保持一致，未修改依赖或重启现有服务。当前Electron供应商选择/连接表单截图已存档，弹窗回到供应商目录。
