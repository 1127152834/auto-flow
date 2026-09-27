# 依赖漏洞审计

日期：2026-09-28（Asia/Shanghai）。状态：confirmed（扫描与版本事实）；漏洞在 AutoFlow 中的可利用性：**未知，未做公告 PoC 利用验证**。

## 前端 npm 锁定依赖

源码为 `33ae3aa49600840b1700c83723408c494dc201a8` 加当前工作树。2026-09-28 01:27 起执行只读检查（UTC 2026-09-27 17:27），实际 registry 为 `https://registry.npmjs.org/`，Node v26.7.0、npm 11.19.0。命令为 `npm audit --json` 和 `npm ls --all --json`；没有执行 audit fix、install 或更新锁文件。

**扫描完整返回** `auditReportVersion:2`、`vulnerabilities` 和 `metadata`，无 registry 错误字段，stderr 为空。`npm audit` 退出 1 是检出漏洞，不是扫描失败。该完整性仅指当前 lockfile 的 registry 公告扫描完成，不表示没有尚未公布的漏洞或已覆盖应用逻辑漏洞。

- registry 计数：872 个依赖项；0 critical、0 high、2 moderate、0 low、0 info。
- 两个 moderate 项是**同一依赖链的库与受影响上游包**：`monaco-editor@0.55.1 → dompurify@3.2.7`。不能说是两个独立、已经可利用的应用漏洞。
- DOMPurify 项下含 18 个唯一 GHSA 公告条目，部分公告是 low，但包聚合严重性为 moderate；这不与上面的包级统计矛盾。
- 受影响路径：`node_modules/monaco-editor/node_modules/dompurify`。顶层应用直接依赖的 `node_modules/dompurify` 是 **3.4.15**，本次未被报告为受影响。
- registry 给出的修复建议是 `monaco-editor@0.57.0`，并标记 `isSemVerMajor:true`。这只是扫描器建议；没有在本次修改依赖或验证该升级与现有编辑器的兼容性。

## 实际产物与可达性

置信度：**高**，旧版本确实进入当前前端产物；**未知**，特定公告的触发条件是否能由攻击者控制的输入满足。

`JsEditorDialog.tsx:6-8`、`PythonEditorDialog.tsx` 和 `InjectJsEditorDialog.tsx` 均导入 Monaco。Monaco 不仅声明 DOMPurify 3.2.7 依赖，还在 `node_modules/monaco-editor/esm/vs/base/browser/dompurify/dompurify.js:1` 内嵌该版本源码；`domSanitize.js:3` 使用内嵌副本。当前构建文件 `apps/desktop/out/renderer/assets/AICodeAssistant-BXXEYJZC.js:81927` 实际包含 `DOMPurify.version = "3.2.7"`。因此只看顶层 3.4.15、或仅把根 DOMPurify 版本提高，并不能证明 Monaco 里的旧代码已经消失。

应用自己的 `safeMarkdown.ts:12,36` 导入顶层 DOMPurify；不要把此次 Monaco 间接依赖公告直接说成该应用函数已证实存在 XSS。Monaco 的已读取净化调用使用 allowed tags/attributes、链接协议 hooks 和 DOM/trusted-type 输出；没有为 18 条公告逐一完成输入来源、具体配置和利用前提验证，也没有以 payload 在当前应用中证实执行。

例如 GitHub 公告 [GHSA-v2wj-7wpq-c8vv / CVE-2026-0540](https://github.com/advisories/GHSA-v2wj-7wpq-c8vv) 说明 3.1.3–3.3.1 存在特定 rawtext 上下文中的属性净化绕过；[GHSA-55q2-fjhq-7xh7](https://github.com/advisories/GHSA-55q2-fjhq-7xh7) 针对 IN_PLACE hook 移除后的子树。这些具体条件与“依赖版本匹配”是不同证据。本次直接打开了这两份 GitHub 公告核对，其余表项按本次 registry 原始响应记录。

## 公告清单

下表忠实列出 npm audit 返回的 GHSA 标识、严重性、受影响范围和标题；所有条目指向 DOMPurify，锁定版本为 3.2.7。CVSS 数据保留在原始 JSON 中；其中 score=0 且没有 vector 的条目没有被解释成零风险。

| GHSA | 公告级严重性 | registry 受影响范围 | 原标题 |
|---|---|---|---|
| [GHSA-v2wj-7wpq-c8vv](https://github.com/advisories/GHSA-v2wj-7wpq-c8vv) | moderate | `>=3.1.3 <=3.3.1` | DOMPurify contains a Cross-site Scripting vulnerability |
| [GHSA-h7mw-gpvr-xq4m](https://github.com/advisories/GHSA-h7mw-gpvr-xq4m) | moderate | `<3.4.0` | DOMPurify: FORBID_TAGS bypassed by function-based ADD_TAGS predicate (asymmetry with FORBID_ATTR fix) |
| [GHSA-crv5-9vww-q3g8](https://github.com/advisories/GHSA-crv5-9vww-q3g8) | moderate | `>=1.0.10 <3.4.0` | DOMPurify has a SAFE_FOR_TEMPLATES bypass in RETURN_DOM mode |
| [GHSA-v9jr-rg53-9pgp](https://github.com/advisories/GHSA-v9jr-rg53-9pgp) | moderate | `>=3.0.1 <3.4.0` | DOMPurify: Prototype Pollution to XSS Bypass via CUSTOM_ELEMENT_HANDLING Fallback |
| [GHSA-hpcv-96wg-7vj8](https://github.com/advisories/GHSA-hpcv-96wg-7vj8) | moderate | `<=3.4.5` | DOMPurify: Cross-realm IN_PLACE sanitization leaves executable markup intact via realm-bound `instanceof` checks |
| [GHSA-r47g-fvhr-h676](https://github.com/advisories/GHSA-r47g-fvhr-h676) | moderate | `<=3.4.5` | DOMPurify: IN_PLACE mode preserves attributes of a clobbered root element, allowing XSS via attacker-controlled root DOM |
| [GHSA-rp9w-3fw7-7cwq](https://github.com/advisories/GHSA-rp9w-3fw7-7cwq) | moderate | `<=3.4.6` | DOMPurify IN_PLACE Sanitization Bypass via Attached Shadow Root Inside <template>.content |
| [GHSA-c2j3-45gr-mqc4](https://github.com/advisories/GHSA-c2j3-45gr-mqc4) | low | `<=3.4.11` | DOMPurify: `CUSTOM_ELEMENT_HANDLING` bypasses `afterSanitizeElements` for allowed custom elements. |
| [GHSA-cmwh-pvxp-8882](https://github.com/advisories/GHSA-cmwh-pvxp-8882) | moderate | `<=3.4.10` | DOMPurify: Permanent `ALLOWED_ATTR` pollution via `setConfig()` bypassing the hook clone-guard (incomplete fix of the 3.4.7 hook-pollution patch) |
| [GHSA-vxr8-fq34-vvx9](https://github.com/advisories/GHSA-vxr8-fq34-vvx9) | low | `<3.4.9` | DOMPurify: Trusted Types policy survives `clearConfig()` and can poison later `RETURN_TRUSTED_TYPE` output |
| [GHSA-gvmj-g25r-r7wr](https://github.com/advisories/GHSA-gvmj-g25r-r7wr) | low | `>=3.0.0 <=3.4.7` | DOMPurify: SAFE_FOR_TEMPLATES bypass - template expressions survive sanitization inside <template> content when using DOM output modes |
| [GHSA-x4vx-rjvf-j5p4](https://github.com/advisories/GHSA-x4vx-rjvf-j5p4) | low | `<=3.4.6` | DOMPurify: `IN_PLACE` mode trusts attacker-controlled `nodeName` on live non-form nodes, allowing script retention and XSS via attacker-supplied DOM objects |
| [GHSA-76mc-f452-cxcm](https://github.com/advisories/GHSA-76mc-f452-cxcm) | moderate | `<3.4.7` | DOMPurify: Hook mutation of `data.allowedTags` / `data.allowedAttributes` permanently pollutes `DEFAULT_ALLOWED_TAGS` / `DEFAULT_ALLOWED_ATTR` |
| [GHSA-39q2-94rc-95cp](https://github.com/advisories/GHSA-39q2-94rc-95cp) | moderate | `<=3.3.3` | DOMPurify's ADD_TAGS function form bypasses FORBID_TAGS due to short-circuit evaluation |
| [GHSA-cjmm-f4jc-qw8r](https://github.com/advisories/GHSA-cjmm-f4jc-qw8r) | moderate | `<=3.3.1` | DOMPurify ADD_ATTR predicate skips URI validation |
| [GHSA-cj63-jhhr-wcxv](https://github.com/advisories/GHSA-cj63-jhhr-wcxv) | moderate | `<=3.3.1` | DOMPurify USE_PROFILES prototype pollution allows event handlers |
| [GHSA-h8r8-wccr-v5f2](https://github.com/advisories/GHSA-h8r8-wccr-v5f2) | moderate | `<3.3.2` | DOMPurify is vulnerable to mutation-XSS via Re-Contextualization |
| [GHSA-55q2-fjhq-7xh7](https://github.com/advisories/GHSA-55q2-fjhq-7xh7) | moderate | `<=3.4.12` | DOMPurify: IN_PLACE hook removal leaves a detached subtree executable, causing XSS |

## 安装树与 lockfile 一致性

逐一读取 lockfile 记录路径处的 package.json：872 条非根记录中，1 条 workspace link、775 个已安装包、96 个当前平台不适用的 optional 包；已安装包 **0 版本偏差、0 必需包缺失**。另行校验 96 个 optional 缺省项没有适用于当前 darwin/arm64 却缺失的条目。没有重下载 tarball 或逐字节校验 node_modules 文件，因此不能宣称安装文件完整性已做密码学复验。

但是 `npm ls --all --json` **退出 1 / ELSPROBLEMS**，指出一个实际依赖树约束问题：

- `@hookform/resolvers@5.9.1` 的 optional peer 要求 `ajv:^8.12.0`；当前解析到 `node_modules/ajv@6.15.0`。
- 该 6.15.0 与 lockfile 一致，属于**锁定安装树本身的 peer 不满足**，不是本机偷偷漂移出 lock。
- 当前 renderer 业务源码中检索到的使用为 `@hookform/resolvers/zod`，未发现 ajv resolver 使用；现有 typecheck/lint/build 均已实测通过。不能仅凭此问题宣称当前业务表单失效，但工程依赖树检查并非绿色。

`package-lock.json` 前后 SHA256 均为 `3b4cc926137f033edb818bf6a41b3c50b85a60561f655df0434c47427abae205`。

## 原始证据

- [npm-audit.json](dependencies/npm-audit.json)：未经裁剪的 registry 漏洞响应。
- [npm-audit-metadata.json](dependencies/npm-audit-metadata.json)：registry、时间、命令边界、源码/锁摘要、退出码与覆盖结论。
- [npm-audit.stderr.log](dependencies/npm-audit.stderr.log)、[npm-audit.exit-code](dependencies/npm-audit.exit-code)。
- [npm-ls.json](dependencies/npm-ls.json)、[npm-ls.stderr.log](dependencies/npm-ls.stderr.log)、[npm-ls.exit-code](dependencies/npm-ls.exit-code)。
- [npm-lock-install-comparison.json](dependencies/npm-lock-install-comparison.json)：逐路径版本比较与局限。

本节未执行依赖修复或改变业务源码。后端 Python 依赖扫描由同次审计的后端结果单独记录。
