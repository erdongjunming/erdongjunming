# 验收矩阵与端到端场景

本文件规定要制作与执行的测试，不是已通过的平台测试记录。固定样例已做计划层核对；业务测试在对应模块实施后执行。

## 1. 模块到接口矩阵

| 生产模块 | 输出端口/对象 | 消费模块 | 必须一致的语义 |
|---|---|---|---|
| M01 | State/Action/Task/所有 Schema | 全部 | 版本、字段、类型、哈希、错误枚举 |
| M02 | RuntimePort → TransitionResult | M04/M05/M06/M09/M11 | COPY 方向、ADD 截断、入参不改、错误分类 |
| M03 | VerifierPort → Verification/Audit | M05/M06/M07/M09 | Task.initial 保持基准、事实判定、独立公式 |
| M04 | StorePort → Observation/Receipt/Export | M07/M09/M10 | 去重、revision、预算、结束锁定、快照来源 |
| M05 | TaskRepositoryPort → Task/digest | M10/M09 | 冻结集合、顺序、可达、答案不泄漏 |
| M06 | DecisionFactory/DecisionPort | M07/M10 | 候选不执行、查询有计量、预算停止 |
| M08 | DecisionFactory/DecisionPort/Usage | M07/M10 | 完整响应转换、错误/用量、真实协议证明 |
| M07 | OrchestratorPort → RunSummary | M09/M10 | 闭环、预测不当事实、最后动作可成功 |
| M09 | EvaluationPort → 报告/Audit | M10/M11 | 完整分母、回放验证、未知成本 |
| M11 | WorldModelPort → Prediction | planner/M07 | 可拒绝、版本、查询计量、数据不泄漏 |

## 2. 公共验收案例

| 编号 | 输入/操作 | 必须得到的结果 | 负责测试 |
|---|---|---|---|
| C01 | State [1,2,3,4]、键顺序不同 | 相同固定 state_id | M01 |
| C02 | r0=7, ADD(0,2) | r0=8，不为 9 | M02/M03 |
| C03 | COPY(source=0,target=3) | [1,2,3,1] | M02/M03 |
| C04 | SET index=true、小数索引、额外字段 | malformed_action；State 不变 | M02 |
| C05 | 只允许 ADD，提交合法 SET | action_forbidden；invalid；一次尝试 | M02/M04 |
| C06 | 相同 Command 重复、关闭后重开重复 | 原 Receipt 相同，Runtime 一次，总尝试 1 | M04 |
| C07 | 相同 command_id 改 Action | idempotency_conflict；原记录不改 | M04 |
| C08 | 新 key 携带旧 expected_revision | rejected/state_conflict；无新尝试 | M04 |
| C09 | 非法动作 envelope 合法、版本当前 | invalid；State 不变、revision+1、attempt+1 | M04 |
| C10 | Snapshot fork 后 SET child | parent/snapshot 未变，预算共享 | M04 |
| C11 | 20 次尝试后恢复新分支 | remaining=0；新动作拒绝 | M04 |
| C12 | 最终 [2,1,0,4]，swap-demo | preserve_violation，success=false | M03 |
| C13 | FakeRuntime 将 COPY 反向/ADD 未截断 | 审计失败，不出成功报告 | M03/M07 |
| C14 | 模型预测完成、实际 ADD(0,0) | 不宣告 success | M07 |
| C15 | 模型持续无效候选 | max_decisions/max_proposals 内终止 | M07 |
| C16 | 最后一次合法动作恰好达到目标 | success，即使剩余动作预算为 0 | M07 |
| C17 | 精确3次+预测2次，规划限额5 | 下一次查询拒绝；总数5 | M07 |
| C18 | 两家不同协议相同合法动作意图 | 都转成相同 Action/Candidate 契约 | M08 |
| C19 | provider 用量缺失、一次限流重试 | 调用次数真实，unknown tokens/cost 为 null | M08/M09 |
| C20 | 已完成 run 的新动作 | run_closed；原命令可重取原 Receipt | M04 |
| C21 | 两连接竞争相同 revision，不同 key | 一条 applied，一条 state_conflict | M04 |
| C22 | 篡改 export 的 State/预算事件/来源 snapshot | replay.valid=false | M09 |
| C23 | 无 API key、只跑 demo | 离线成功，不联网 | M10 |
| C24 | 未知条目预测 | abstain、next_state=null，事实不受影响 | M11 |

## 3. 组合测试的所有权

集成人 M00 在 `tests/integration/` 制作如下测试，下游只能提供复现资料和建议，不抢写此目录：

- `test_ports.py`：所有具体对象可赋给相应 Protocol，并由 mypy 检查。
- `test_offline_run.py`：Runtime+Verifier+Store+Heuristic+Orchestrator，swap-demo 一次成功，最终 State=[2,1,3,4]。
- `test_retry_recovery.py`：数据库提交后丢响应，重开、重复命令，只有一个 attempt。
- `test_branch_budget.py`：fork 恢复、parent/child 隔离、预算共享。
- `test_false_prediction.py`：假成功预测、非法提案、查询预算、最后一次成功。
- `test_adapter_switch.py`：Scripted、ChatCompletions fake、Messages fake 更换无需修改 Runtime/Store；真实测试单独显式 live 标记。
- `test_reports_replay.py`：批量失败分母、未知成本、导出篡改被拒绝。
- `test_cli_release.py`：subprocess 跑 demo→导出→replay，退出码和路径有效。

## 4. 一条固定组合轨迹

1. create_run("run-001",golden.task,"main-001") → 初态 [1,2,3,4]、revision 0。
2. snapshot("snap-001") 保存该状态。
3. 执行 command cmd-001、revision 0、SWAP(0,1) → applied、attempt_index1、revision1、[2,1,3,4]。
4. 同 cmd-001 再执行 → 原 Receipt、预算不变。
5. 独立 check → success=true；finish_run 保存 summary，run 结束。
6. 重开 Store，observe 与原状态相同，cmd-001 仍可读取原 Receipt。
7. 新 cmd-002 在同 run 请求任何动作 → run_closed，无变更。
8. export/replay → valid=true；把 after.registers[0] 改成 -8 → valid=false。

分支演示使用另一个尚未结束的 run，不能在步骤 5 以后继续 fork；这样与结束锁定一致。

## 5. 命令与预期

由实际仓库虚拟环境运行：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/contracts -q
& .\.venv\Scripts\python.exe -m pytest tests/env tests/verification tests/storage -q
& .\.venv\Scripts\python.exe -m pytest tests/tasks tests/planning tests/orchestration tests/evaluation tests/cli -q
& .\.venv\Scripts\python.exe -m pytest tests/adapters -q
& .\.venv\Scripts\python.exe -m mypy src
& .\.venv\Scripts\python.exe -m pytest tests/integration -q
```

预期：已实现阶段全部命令退出 0，无未说明的 skip/xfail；live 标记只在有显式配置时运行。尚未实施的目录不应假造测试结果，阶段状态仍未通过。

每次修复新问题才增加相关回归测试；已通过检查无代码变化不重复无意义的大批运行。

## 6. 阶段交付清单

G0：冻结提交、契约摘要、Schema/type/port 检查、样例验证、依赖图与文件所有权检查。

G1：T01-T16、V01-V03、C05-C13/C20-C21 的实际测试结果；数据库恢复、竞争、快照和预算证据。

G2：30 smoke、100 dev 三种离线方法的结果；完整分母、事实轨迹、回放证据、CLI 与安装说明、release 标签。

G3：两个不同协议真实 provider/model 各至少 10 个有效调用的脱敏证据；错误、重试、未知用量假响应测试；明确解题率与协议率。

G4：数据/训练/模型版本、去重与切分审计、单步和多步指标、拒绝覆盖率、公平规划和成本对照；负结果也属于合格研究交付。

## 7. 这份计划本身的核对

静态核对包括：JSON 可解析、Schema 合法、公共样例合 Schema、.pyi 可解析、字段/枚举/端口引用一致、模块依赖无环、文件所有权不重叠、动作样例人工公式一致、状态哈希一致、文档引用有效。

上述核对证明制作规格内部一致，不证明尚未编写的平台已经通过业务测试。计划包验证记录另见 `07-plan-verification.md`。
