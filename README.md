# AI 程序世界实验平台

可验证、可回放、兼容可替换模型的程序执行与世界模型实验平台。

当前仓库保存 **v1.0 多模型制作计划**，尚未实现应用。先在现有操作系统上建立确定性执行、独立验证与评测闭环，再研究表示、预测和规划。

## 从这里开始

- [完整制作计划与执行顺序](docs/plan-v1/00-README.md)
- [公共接口与行为契约](docs/plan-v1/01-contract.md)
- [多模型对接与合并规约](docs/plan-v1/02-integration.md)
- [12 个模块任务卡](docs/plan-v1/03-modules/)
- [模型派发提示词与交接模板](docs/plan-v1/04-handoff-prompts.md)
- [世界模型研究路线](docs/plan-v1/05-research-roadmap.md)
- [验收案例与组合测试](docs/plan-v1/06-acceptance.md)
- [计划一致性校验记录](docs/plan-v1/07-plan-verification.md)
- [模块依赖与文件所有权清单](docs/plan-v1/module-manifest.json)

## 协作顺序

先完成 M00 工程底座，再完成 M01 公共契约。冻结同一提交与契约摘要后，各模型在独立分支和工作树中制作分配模块。集成人按依赖顺序合并并复测。

每个执行者必须提交实现、测试、契约摘要和交接单；模块独立测试通过后仍须组合验收。计划校验通过不代表应用已实现、真实模型已兼容或研究增益成立。

## 复测计划

使用 Python 3.14，在仓库根目录创建独立环境：

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install jsonschema==4.25.1
& .\.venv\Scripts\python.exe docs/plan-v1/tools/verify_plan.py
```

macOS/Linux 使用 `.venv/bin/python` 替换上面的 Windows 解释器路径。

计划包含 25 个文件、12 个模块任务卡和 24 项验收案例。公共契约文件位于 `docs/plan-v1/contracts/v1/`；它们是规格参考，并非已经实现的应用代码。
