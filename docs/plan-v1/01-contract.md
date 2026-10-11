# 公共契约 v1.0.0

## 1. 契约来源与布局

唯一协议：`schema_version = "1.0.0"`，环境：`env_version = "reg4/1.0.0"`。

`contracts/v1/schema.json` 定义可交换 JSON；`types.pyi` 对应公共类型，`ports.pyi` 对应 Python 调用；本文定义 Schema 无法表达的跨字段与行为约束。三个层面的不一致阻断 G0，由 M01 统一修正。

实际仓库中规范文件放在 `contracts/v1/`，可运行公共类型与 Protocol 放在 `src/world_model_lab/contracts/`。M01 将参考 `.pyi` 转成真实 `.py`，只允许结构验证和类型定义，不放运行、规划或存储实现。各业务模块不得自己复制公共类型。

JSON 使用 UTF-8；拒绝重复键、NaN、Infinity、过量嵌套、超出大小限制的输入。整数不接受 `true`/`false`；Python 的 `bool` 是 `int` 子类，需要显式拒绝。核心对象禁止未知字段，增加字段走契约版本变更。

## 2. 状态与标识

`State` 只有 `env_version` 与长度为 4 的 `registers`；每个整数在 [-8, 8]。`state_id` 是规范化 State 的 SHA-256：

```python
payload = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
state_id = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

例：`{"env_version":"reg4/1.0.0","registers":[1,2,3,4]}`。规范化只在通过结构验证后进行，不忽略非法字段或强制转换数字。

`state_id` 是内容标识，不是“当前版本”。内容相同的两个分支可以有相同标识。`Observation` 含 `branch_id`、单调递增 `revision`、`state_id`、完整 `state`；并发写入用 `expected_revision`，不能只用内容哈希判断新旧。

`run_id`、`branch_id`、`snapshot_id`、`command_id`、`candidate_id`、`request_id`、`task_id` 为 1 至 128 位 ASCII 标识，匹配 `[A-Za-z0-9][A-Za-z0-9._:-]*`。实现可使用 UUID 字符串，测试注入固定 ID。时钟使用 UTC 记录，持续时间使用 monotonic；时间不进入状态哈希。

公共 TypedDict 在 Python 中可变，所有模块以值语义交换：入参不变、出参深复制、快照独立；不能共享可写的 `registers` 列表。测试必须主动修改返回对象检查隔离。

## 3. 动作规则

| JSON 动作 | 真实转移 | 特例 |
|---|---|---|
| `{"op":"SET","index":i,"value":v}` | r[i] = v，v ∈ [-8,8] | 原值相同仍是有效动作 |
| `{"op":"ADD","index":i,"delta":d}` | r[i] = min(8,max(-8,r[i]+d))，d ∈ [-2,2] | d=0 有效 |
| `{"op":"COPY","source":i,"target":j}` | r[j] = r[i] | 方向固定为 source 到 target；i=j 有效 |
| `{"op":"SWAP","left":i,"right":j}` | 交换 r[i] 与 r[j] | i=j 有效 |

索引只允许 0/1/2/3 的整数。非法结构、未知操作、越界数值、额外字段、布尔值，以及任务禁用的动作均返回失败且不改变 State。

动作错误检查顺序固定：结构和字段类型 `malformed_action` → 字段数值范围 `invalid_argument` → 任务合法集合 `action_forbidden`。同一输入只有一个主错误；固定样例据此对照。

纯 Runtime 接收 `action: object`，允许调用方把坏输入交给它核验；它返回 `TransitionResult`。不执行字符串求值、不读写外部文件、不持有运行预算。环境只返回已知的动作事实，当前没有随机转移。

## 4. 任务和目标

`Task` 指定初始 State、目标、合法操作列表、seed 和四项限额。限额默认建议：`max_attempts=20`、`max_decisions=20`、`max_proposals=40`、`max_plan_evaluations=5000`；它们是不同单位。

`Goal.targets` 是指定最终值的索引/值对；`Goal.preserve` 指定最终必须等于该任务最初状态的寄存器。两个列表内部必须唯一；允许同一索引同时出现，只有目标值等于最初值时才合法。至少存在一项目标或保持要求。

`preserve` 在 v1 只检查最终状态，不是“过程永远不能修改”。若将来需要路径约束，必须新增协议与检查任务，不能偷偷改变含义。快照、分支后的保持基准仍是 Task.initial，不是分支出生状态。

任务合法动作列表不可为空，不含重复项。任务生成的答案轨迹和最短路径资料写入 `tasks/private/`，不进入模型请求。四个 SET 能解决的简单任务只验流水线，不能宣称体现长期规划能力。

## 5. 预算归属

所有限额按 run 计，所有分支共享，SQLite 持久化，不能随快照恢复重置。

| 预算 | 消耗时机 | 不消耗的情况 |
|---|---|---|
| 动作尝试 | 合法新命令通过 revision 检查后，Runtime 被调用一次；非法动作也消耗 | 同内容重试、revision 冲突、预算已耗尽 |
| 决策次数 | 每次实际调用 DecisionPort 前预留一次；失败也消耗 | 返回的结果被重复读取 |
| 候选数量 | Decision 返回每一个候选时；结构坏的候选也占一次 | 新预算不因丢弃候选返还 |
| 规划评估 | 调用计量包装器中的精确 transition 或预测器时 | 读取缓存不算模型调用，但单独报告 cache_hits |

决策返回数量大于剩余候选预算时，整批拒绝，预算扣除到 0，返回 `budget_exhausted` 并终止。不能先选择超预算候选中的“最好一个”。`Decision` 最大 8 个候选，每个候选最多 20 个动作。

M07 持有的计量包装器计数；不能依赖模型自报成本。真实执行次数不算进规划评估，但计入动作尝试。planner 只能拿到包装后的 pure Runtime/WorldModel，不能拿 Store 来试执行。

时间与 API 金额限额位于 RunConfig，由 M07/M08 执行，绝不依赖模型字段。Unknown usage 用 null，不填 0。确定性预算（次数）和外部等待超时分别管理。

## 6. 幂等命令与事务

`Command` 的 run/branch/revision/command_id 由 M07 产生。模型只提供 Action，不得自选 run_id 或注入快照权限。

SQLite 中 `(run_id, command_id)` 唯一。Store 的 `execute(command, runtime)` 在一个写事务里完成：查重复 → 检查 run/branch → 检查 revision → 检查动作预算 → 预留一次尝试 → 调纯 Runtime → 写新 Observation 与 Receipt → 提交。

相同 key、相同规范化 Command：返回原 Receipt，不再执行或扣预算；提交成功但响应丢失后也适用。相同 key、不同 Command：抛 `PortError("idempotency_conflict")`，原 Receipt 不覆盖，也不为冲突请求伪造 Receipt。未知 run/branch 用 `PortError`，不伪造 Observation。

run 初始为 running；`finish_run(run_id,summary)` 原子保存最终摘要和结束事件，转为 finished。同摘要重复结束为 no-op，不同摘要冲突报 storage_error。结束后新动作、预算预留、快照和分支请求报 run_closed；已经提交的相同 Command 仍可读取原 Receipt，去重检查先于 closed 检查。

revision 冲突返回 `StepReceipt.disposition="rejected"`，错误 `state_conflict`；before/after 均为当前 Observation，无扣动作预算。动作预算耗尽也返回 rejected。rejected 命令也写去重记录，以后相同 key 得到相同结果；刷新 revision 后重试必须用新 key。

Runtime 返回 accepted=true：Receipt 为 `applied`。Runtime 返回 accepted=false：Receipt 为 `invalid`。两种情况 revision 都加 1，attempt_index 为 run 的全局动作尝试序号，从 1 开始。invalid 的 State 不变，但观察版本已变。

rejected 的 attempt_index 为 null，revision 不变。数据库异常应回滚完整事务，使用 `PortError("storage_error")`，不把失败写成成功。并发写事务必须串行化，冲突按上述规则返回；busy 重试有界，不无限等待。

Store 的 create_run 同 run_id 第二次调用报 `run_exists`；fork 同 branch_id 报 `branch_exists`。它们不是可重复调用的 step 命令。SQL 参数必须参数化，不拼接 ID。

## 7. 快照、分支与恢复

Snapshot 保存当前 Observation 的不可变副本。fork(snapshot_id,new_branch_id) 在同 run 新建分支，State 与 snapshot 相同，revision 从 0 起，记录来源 snapshot_id 和来源 branch_id。

v1 的“恢复”是从快照 fork 新分支，再把该分支作为 active branch；原分支和历史不删除、不改写。这样避免预算回退与时间线覆盖歧义。M07 记录 branch selection；一次 run 最多创建 16 个分支及 64 个快照，超限报 `branch_limit`/`snapshot_limit`。

快照只承诺这四个寄存器的内部状态恢复。它不包含 API 会话、文件、网络、运行时进程或 GPU 内存。SQLite 存在的记录不是外部系统可回滚的证明。

v1 中模型无权调用 snapshot/fork；研究脚本和编排器可调用。CLI 提供单独快照演示，不默认在每次规划时自动复制分支。

## 8. 候选、预测和真实执行

`DecisionPort.decide(request)` 返回 Decision，status 为 `candidates`/`stop`/`error`。candidates 非空只允许 candidates；stop 无候选无错误；error 无候选且有错误。

每个 Candidate 含 actions、source、prediction_kind、predicted_states、confidence。prediction_kind=none 时 predicted_states=null；exact/learned 时数组长度与 actions 相同，均为预测。`confidence` 可为 null；只有经验证校准且声明语义的后端才填写 [0,1] 数值。

M07 按候选返回顺序选第一个结构合法、任务允许的候选，只执行其首个动作，读真实 Observation，再决策。Candidate 的其余动作是规划意向，不成为待执行的自动队列。不同排序算法在生成侧实现并记录方法配置。

生产 DecisionPort 应返回完整合法的 Decision；M08 在解析厂商原始格式时拒绝坏响应。M07 仍防御性检查：能安全读到候选列表时先按其长度消耗提案预算，再作严格结构验证；结构坏的整批拒绝，结构合法但动作被任务禁用的候选逐项跳过。这样不会因校验失败返还已经生成的提案预算。

模型说任务完成仍需 M03 检查真实 State；预测中出现达到目标的状态不能结束 run。M03 审计不通过时 run=`audit_failed`，不允许报成功。

`WorldModelPort.predict(state,action)` 的 Prediction status 为 predicted 或 abstain；后者 next_state=null。模型未知环境版本或无法支持动作必须拒绝。预测器不能调用 Store 或修改任务初始值。

M07 把真实 history、当前观察和剩余预算传入 DecisionRequest。没有下一步真实状态、生成器答案轨迹或私有最短路径。精确搜索本来就知道规则，属于单独标注的 oracle 基线，不能包装为 LLM 学习收益。

## 9. 错误与适配器

所有公共失败使用 ErrorInfo 或 `PortError`，code 来自 Schema 枚举。`PortError.code` 与 error code 一致，message 是面向调试的摘要，不作为程序分支依据。

模型后端错误：`provider_timeout`、`provider_rate_limited`、`provider_auth`、`provider_unavailable`、`provider_protocol`。错误格式、未知工具、缺少字段与禁止参数映射到 `provider_protocol`，不能当合法 Action 执行。

真实后端每个 decide 最多 2 次 HTTP 尝试；超时、429、临时 5xx 可以在预算内再试一次；认证、余额/权限失败和格式错误不自动重试。每次重试记录调用及可能未知的用量。调用时间默认上限 30 秒；没有取消能力的线程不得宣称调用已中止。

v1 为同步接口；真实传输层使用有超时的 HTTP 客户端，串行 run，不做流式工具自动执行。流式输出如未来加入，先组装完整响应、验证、再提 Candidate。

不同品牌会话不直接搬运原始思考签名或私有续接字段。v1 使用中立的 DecisionRequest 构造每轮请求，厂商私有字段留在 adapter 内；跨品牌切换以新的请求重建上下文。

## 10. 持久化与报告

M04 管表：runs、branches、snapshots、commands、control_events、budget_events。commands 保存完整 Command/Receipt 与规范化 command_digest；原始 Provider 文本放在单独的受限证据文件，由 M08 管理，默认不写密钥或 Authorization。

M09 只通过 StorePort 的导出方法读取，不查询 SQLite 内部表。导出 commands/receipts 两个数组按持久化的 command_seq 顺序一一对应，包含 rejected；具有 attempt_index 的动作事实可按该序号核算。控制事件、budget_events 分别按自身 event_seq 排；重复 command_id 只一条记录。budget_events 的 kind/count 累加必须等于 budget；最终摘要放 final_summary，未结束为 null。

RunSummary 包含任务、最终独立验证、事实计数、测得时间与来源信息。api tokens、金额未知时为 null。成本相加有未知项时该合计也为 null，另显示已知部分与未知条数。

RunSummary.final_observation 指明实际结束的分支、revision 与完整 State；其 state_id 必须等于 final_verification.state_id，重新执行 verifier.check 得到相同验证结果。final_summary 不能只凭模型文字或某个其他分支的成功状态填充。

record_control 对外只接受 branch_selected、decision_recorded、provider_usage。snapshot_created/branch_created/run_finished/run_cancelled 由相应 Store 方法内部生成；记录 branch_selected 时核对 branch 属于 run。结束后的任何新控制写入也报 run_closed。

语义回放指 initial + 已提交动作按 attempt_index 重算，再核对 before/after、state_id、分支来源与预算。ID、机器运行时间、UTC 记录允许不同，寄存器轨迹和动作 disposition 必须一致。

## 11. 兼容与接口变更

相同 v1.0.0 下字段、含义、错误优先级、COPY 方向、预算、快照恢复方式都不能由单模块改变。新增可选能力先申请小版本；改变含义、删除字段、新动作环境或真实代码系统使用大版本和新的 env_version。

运行时只有列入 compatibility.json 的版本组合可启动，不能仅用字符串前缀宽松匹配。v1 初始只允许契约 1.0.0 与 reg4/1.0.0。

M01 计算契约摘要：对 schema.json、types.pyi、ports.pyi、golden.json 的相对路径及各 SHA-256 排序，写为固定换行文本，再对 UTF-8 文本 SHA-256。类型参考和行为规格的版本由人工核验；同时记录本文文件摘要，行为变化也须升级冻结包。
