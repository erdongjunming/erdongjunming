# 多模型对接与合并规约

## 1. 一个集成入口

所有模块在同一仓库制作，各模型拥有独立分支/工作树。集成人宣布一个冻结提交；执行者只能基于该提交开始。开发阶段不要让多个模型在同一物理工作树同时改文件。

原始代码可以经本地分支或补丁交接；无需提前配置 GitHub。推送、公开发布、发送外部信息不属于本计划的默认动作。

M00 唯一管理 pyproject.toml、依赖锁、根 README、统一检查脚本与组合测试。M01 唯一管理公共契约。业务模块只写 `module-manifest.json` 对应路径。全局新增依赖需要在交接中提申请，由 M00 安装、验证、锁定；不要由各模型修改一遍依赖配置。

## 2. 所有权与依赖纪律

允许 import 的边界：

- M02/M03：只导入标准库和公共 contracts；M03 不导入 M02 的计算规则。
- M04：标准库、contracts；Runtime 由参数注入，不导入具体 RegisterRuntime。
- M05/M06：contracts；Runtime/Verifier 由参数注入。任务答案不得导入 planner。
- M07：contracts；通过构造参数注入所有端口，不直接导入具体 Store/Adapter/Planner。
- M08：contracts、批准的传输库；不导入 Store、Runtime、Verifier。
- M09：contracts；通过参数注入 Orchestrator/Runtime/Verifier，不读 storage 内部表。
- M10：组合根，可以导入各具体实现，用配置创建实例。
- M11：contracts 和批准的研究库；不导入 Store、不写事实记录。

只有 M10 和测试组合根连接实现。这是单向依赖，不让“统一 controller”成为所有模块都能互相调用的入口。

M06 的计量包装器接口由 M07 管理：执行者可先用 RuntimePort/WorldModelPort 的假实现测试；生产装配时 M07 传入计量后的端口。planner 无权访问未计量的 oracle。

## 3. 每个模块的最小交付

1. 实现与测试在独立提交中，无伪造通过日志。
2. 公共方法完整符合端口，不仅是方法名字相同。
3. 自己的测试通过，公共契约测试通过，mypy 可检查端口装配。
4. 可运行的离线最小例子、失败例子和已知限制。
5. `handoff.json` 包含清单要求字段；记录准确命令、退出码、测试数量、执行时间和证据路径。
6. 新增依赖、接口请求、模拟结果、真实调用分别说明。

模块没有完整测试证据时状态最多 `in_progress`。模块独立通过后可 `review_ready`；组合仓库复测后才 `accepted`。

## 4. 合并顺序与工作树示例

以下在 M00 初始化的仓库内执行，分支不存在时创建，存在时先核对，不删除用户分支：

```powershell
git switch -c integration/v1
git worktree add ..\AIProgramWorldLab-M02 -b module/M02
git worktree add ..\AIProgramWorldLab-M03 -b module/M03
```

派发记录需要实际 base_commit；不把上面命令当成已执行。工作树共用 Git 对象但有各自虚拟环境，不能共用可写数据库；所有测试使用临时数据库。

合并 M02 后，M03 不会自动取得 M02 的新内容。集成人明确告诉下游新的冻结提交；下游先提交自身工作，再合并基准并复测。避免用强制重置处理冲突。

集成顺序：M00 → M01 → M02/M03 → M04/M05/M06 → M07 → M09/M10；M08 离线部分可以穿插，真实组合测试在 G2 后。M11 在研究阶段。

## 5. 接口变更单

```json
{
  "change_id": "CR-001",
  "requesting_module": "M08",
  "current_version": "1.0.0",
  "problem": "具体无法表达的输入或输出，以及可复现案例",
  "proposed_change": "准确字段或方法签名与语义",
  "affected_modules": ["M01", "M07", "M08", "M09"],
  "compatibility": "breaking",
  "migration": "如何转换旧记录，或为什么必须保留旧环境",
  "tests_to_change": ["具体测试路径和新增失败案例"],
  "approval_status": "proposed"
}
```

未批准变更不进入业务分支公共接口。M01 检查全部生产者和消费者，发布新 Schema、类型、样例、摘要、迁移说明；M00 用组合测试确认后形成新的冻结提交。不要用 `**kwargs`、宽松 JSON、额外 dict 字段或兜底字符串绕开版本问题。

## 6. 自动对接检查

统一脚本必须顺序执行：契约摘要与版本检查 → schema/type/sample 一致性 → import 边界 → 模块测试 → 类型检查 → 组合测试。前一步失败不得把整条检查标成通过。

公共契约测试必须用真正的 JSON Schema validator（jsonschema Draft202012Validator），不能手写一个只检查顶层键的替代器。`check_schema` 验证文档，目标对象用 `$ref` 到对应 `$defs` 验证；随后进行目标冲突、长度对应等语义检查。

纯类型一致性示例：

```python
runtime: RuntimePort = RegisterRuntime()
verifier: VerifierPort = IndependentVerifier()
store: StorePort = SQLiteStore(db_path)
planner: DecisionPort = HeuristicPlanner(verifier)
```

该示例放在 M00 的 integration 装配测试，并由 mypy 检查；业务模块不凭自己打印“兼容”代替赋值验证。

## 7. 组合故障归属

| 症状 | 先检查 | 不应采用的处理 |
|---|---|---|
| COPY 方向与预期不同 | M01 样例、M02、M03 | 同时改两个模块直到它们碰巧一致 |
| 恢复后多了预算 | M04 的 run 预算与分支来源 | 改报告隐藏多执行动作 |
| 同一命令执行两次 | M04 事务、命令摘要、唯一键 | 在适配器里忽略重复文本 |
| 假预测导致报成功 | M07 是否独立验收、M03 实际 State | 提高模型自评阈值 |
| 一家模型可以、另一家失败 | M08 厂商响应转换和会话处理 | 修改 Runtime 去识别厂商 JSON |
| 冻结任务结果变化 | task digest、env_version、随机种子 | 重新生成一套更容易的任务覆盖旧集 |

## 8. 证据与版本

`artifacts/<gate>/<module>/` 保存测试输出、摘要和交接。运行数据放 `runs/`，机器学习数据放 `research/data/`，均不默认提交大型文件；提交清单、配置、哈希和可复现生成流程。

密钥只通过环境变量或本机凭据注入，配置样例只写变量名。控制事件、报告、异常和录制样例不含密钥。运行时要求先确定输出路径，不写入源码目录。

完成 G2 时建立 release/v1-offline 标签；完成 G3 时建立 release/v1-models 标签，记录真实访问的 provider/model。研究版本单独命名，并保留离线版本可运行。
