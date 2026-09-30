# PM9 启动失败与记录再次领取

2026-09-24 DATA-CLAIM-03启动失败修复（confirmed本机源码/新包回归子范围）：a7059dc6修正真实子进程finished/failed在ready前被误判interrupted；只接受启动前失败/取消，保留身份、清理、退出与所有权检查。真实2场景证明失败占名额、非空状态/值/版本不变、释放后同记录可再取及同键无重复；8项协议反向/终态检查通过，相关81 passed/3 skipped。最终完整后端3505 passed, 86 skipped, 2 warnings in 911.71s，Ruff/mypy408、4映射/251引用、后端构建与未签名ARM完整桌面passed/24截图；清理界面已目视复核。前端未变，保留7b896163的5475/409原范围。仅DATA-CLAIM-03 planned→partial，合计208partial/43planned/0verified、249有断言/2未定位，缺口241生产/19实现/8测试/24外部不变。CLI401仍阻断当前新矩阵，打包启动失败UI与系统性资源故障受阻组合待补；releaseAccepted=false。见startup-failure-follow-through.json。

来源：原始 data-and-state-rules.md DATA-CLAIM-03；生产 worker 协议；本轮真实子进程及受控启动故障测试。Ruling：只修正已确认的启动前失败分类，不把协议异常/缺失清理/进程退出异常降为普通失败，不改准入安全边界。准备夹具错误另存日志，不能作为产品反例；原产品 RED 为 interrupted != failed。

证据整理事故（非产品修改）：临时脚本路径变量复用，首轮通过后将已目视/已hash的一张PNG误写为JSON；原始数据报告和其余23图保留，误写JSON另存。修正脚本后仅重跑同候选完整桌面，第二轮passed，24张PNG签名及hash核对通过；后端全量不重复。两轮性能观察分别记录。
