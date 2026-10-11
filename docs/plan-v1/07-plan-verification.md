# 计划包校验记录

日期：2026-10-11，Asia/Shanghai。对象：本计划包 v1.0.0。结论：计划层结构与固定样例校验通过；应用实施未开始。

## 1. 实际使用的校验环境

Python 3.14.0。公开版本省略本机解释器与用户目录的绝对路径。

仅将校验依赖安装到原工作区 `work/plan-validation-deps`，未安装到全局 Python。版本：jsonschema 4.25.1、attrs 26.1.0、jsonschema-specifications 2025.9.1、referencing 0.37.0、rpds-py 2026.9.1。

随包提供 `tools/verify_plan.py`，依赖 jsonschema。公开版本移除了对原工作区依赖目录的自动搜索；请在独立虚拟环境安装 `jsonschema==4.25.1` 后运行。

## 2. 校验结果

| 检查 | 数量 | 结果 |
|---|---|---|
| Draft 2020-12 Schema 自检 | 1 | 通过 |
| 本地 $ref 引用完整性 | 1 类检查 | 通过 |
| 正向 Schema 样例与 Task | 10 | 通过 |
| bool/浮点/越界/额外字段反例 | 4 | 正确拒绝 |
| TypedDict 字段与 Schema 类型对应 | 32 个定义 | 通过 |
| 公共 Literal 别名与枚举 | 3 | 通过 |
| 端口注解及导入引用 | 27 个方法（含 PortError 构造） | 通过 |
| 模块依赖无环与任务卡存在 | 12 个模块 | 通过 |
| 文件所有权无交叠 | 37 个路径 | 通过 |
| 规范化状态哈希 | 2 | 通过 |
| 动作与错误优先级固定样例 | 16 | 通过 |
| 独立目标检查固定样例 | 3 | 通过 |
| 核心文档存在 | 6 | 通过 |

总计 13 类检查。Schema 整数验证使用严格 TypeChecker，以明确拒绝 Python bool 与 JSON 1.0；这项约束也已写入 M01。

## 3. 冻结参考摘要

契约四文件摘要：`sha256:5d64f2f0b576b5f1d841bdc817c0c8097982a3aa7cd570e5ffd30cf989a98aa5`。

行为说明 01-contract.md 摘要：`sha256:5d208097d6ebdd8b074f761acc4e085f4727d2bf58497fe08bd57e923ce085fa`。

摘要以随包 verify_plan.py 的排序和换行算法为准。首次制作 M01 转成应用中的可运行类型后，应计算实际仓库的冻结摘要并保存提交；不能沿用旧摘要冒充内容未变。

## 4. 复测命令

```powershell
python tools/verify_plan.py
```

原始计划校验退出 0，输出 status=passed。上面是公开版本的等价复测命令，需从 `docs/plan-v1/` 目录执行；仓库根目录的环境准备与复测步骤见根 README。

## 5. 校验边界

脚本验证计划中的 Schema、类型、签名引用、样例公式与依赖/所有权，不执行尚未实现的 Runtime、Store、Orchestrator 或模型 API；它没有进行应用 mypy、pytest、重启或并发业务测试。

动作样例由计划校验脚本按明示公式重新核算，不是调用应用实现。真正的独立验证器测试、对接测试和真实后端调用需要按模块卡与 06-acceptance 实施。

本次未创建 D 盘应用仓库、未下载模型、未调用收费模型服务。交付的是制作计划、公共接口参考、校验工具与校验记录。
