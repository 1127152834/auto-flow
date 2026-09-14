# 图像资源跨端共用样例

2026-09-14，F1有界合同修复。

现有 StudioImageAsset DTO要求size为0至JavaScript最大安全整数、id/name/originalName非空；path可省略并默认null。原前端guard接受小数/不安全整数及空标识，又拒绝省略path，与DTO不同。

新增 apps/backend/tests/fixtures/studio-image-assets.json 共19组双方共用输入和期望。前端读取器补齐path默认值、保留扩展属性，再严格校验整批；任何一项非法时整批拒绝。共享缓存初始化及节点ImagePathInput都使用该读取器，未改写持久化资产或数据库。

初版18例前端6失败、12通过；完成并补零字节边界后，后端19例、前端含相关消费者回归56项通过。额外组件验证省略path时可选择原始文件名。TypeScript、ESLint、Ruff、3项目录检查与renderer/main/preload构建通过。39条新台账。

证据见 evidence/f1-image-shared-contract；未重跑全量、未新增真实宿主或浏览器E2E。资源面板其余读写消费者的校验与并发仍待处理，不把两个消费者的修复标成整个资源领域已完成。
