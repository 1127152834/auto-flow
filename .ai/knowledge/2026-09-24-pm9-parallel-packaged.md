# PM9 并行打包补证与 CI 点击诊断

日期：2026-09-24。状态：confirmed（打包API和脚本复现范围）；完整ARM桌面也已通过；原生CI后续状态以专项报告为准。

来源：`parallel-packaged-follow-through.json`、`ci-metadata-click-follow-through.json`、实际ARM sidecar/worker/browser与GitHub Actions35886627514。生产源码仍69baeeb2，未扩展准入或引入执行器。

- 复用运行脚本新增2/3次并行循环。同名index/saved隔离，五条实际写入、独立公开nodeVisitId、唯一End只关联A-1/B-2到同环境。内部executionContext不是项目公开事件字段；首轮脚本错误已保留，内部scope继续由现有SQL源集成断言证明。
- 并行人工两等待点均只存在一个持久waiting项，普通分支后继未运行；两次继续后声明输出left/right、join/End各一次。重新使用同一automation开新batch，在第一人工点stop后只取消已创建项、不创建下一项、不跑后继/End，前置记录保留。第二轮脚本重复绑定workflow产生409已更正为复用automation，负向报告保留。
- ARM CI后端3486/78skip、前端5473/409通过；打包metadata HTTP69条规则和open_page字段断言通过，之后等待必填提示失败。截图显示节点未选择、配置面板提示选择节点。没有原点击坐标记录，不能断言某一动画就是CI根因。
- 旧点击helper只检查可见，不检查遮挡/移动。在隔离真实Electron用可见但覆盖目标复现未命中；增加命中测试和两个稳定位置采样后同fixture通过。102脚本检查包含回归，既有元数据检查未放宽，15秒等待阈值未增加。该修复针对确定的验收helper缺口；CI原始时序原因置信度中，等待原生后续。
- 使用systematic-debugging、test-driven-development和verification-before-completion技能完成诊断、RED→GREEN和实际复验。无新生产业务代码，故不重复本机全量后端/构建。
- 251台账仍249有断言/2未定位、206partial/45planned/0verified；仅FLOW-A16/XE-C12/XE-G05新增精确子范围。人工finish/到期/额度/在途清理的完整打包组合、Windows/Intel同新增场景及外部验收继续保留。P1–P3代理补充仍待确认。

完整API与完整ARM桌面已通过，21张界面截图；哈希、测量及原生后续见报告；releaseAccepted=false。当前Windows/Intel原job继续，不取消或重开全部矩阵；候选稳定后只对需要的平台发起后续。

后续终态勘误：35886627514三平台均失败，两个Mac均未选中节点；Windows已通过必填检查，重新打开后1008×662紧凑布局隐藏“模块库”导致文字就绪误判。源码确认小屏折叠且放宽不自动展开；prepareStudioView恢复1440×1024并通过既有按钮展开。原单平台后续计划被三平台一次后续取代，尚未触发；没有取消活跃job。最终本机结果另见JSON。

Windows验收helper复现：同包1008×662隐藏模块库，单独放宽1440×1024仍保持折叠；Studio tooltip把title迁到data-tip，选择器兼容两者并通过既有按钮展开后实际就绪。此紧凑→放宽→展开分支加入正式窗口smoke，最终完整桌面仍在跑。该变化不修改生产布局。

最终验证：带紧凑重开回归的完整ARM桌面通过，22张截图；102脚本、4映射和251引用通过，语法/diff检查通过。原三平台失败按各job保留；新矩阵待同候选提交推送后触发。没有生产代码变化，不合并发布。
