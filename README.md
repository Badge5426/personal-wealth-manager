# Personal Wealth Manager / 个人财富管理

面向中国大陆个人用户的可投资财富管理 Skill。它帮助用户整理证券、基金、存款、银行理财、保险现金价值、养老金、收入与支出，在现金安全和风险边界内清理问题资产、保留少数核心资产，并逐步增加可持续的“睡后收入”。

This Codex skill helps individuals in mainland China reconcile investable wealth, cash flow, and risk constraints before simplifying scattered holdings into an understandable, maintainable long-term structure.

## 核心能力

- 先核对资产、成本、现金流、已实现与未实现收益，再做判断。
- 区分客观风险能力、主观风险承受与家庭共同决策，采用最严格的约束。
- 识别重复持仓、主题集中、尾仓、复杂或自己不理解的产品。
- 用“核心仓 + 研究仓”降低投资超市化，而不机械追求回本或频繁交易。
- 同时适用于尚无本金的用户：先改善现金流、健康与可变现能力，再逐步积累金融资产。
- 指数基金审查按需加载，不让主流程变得冗长。

## 安装

在 Codex 中安装此目录：

`skills/personal-wealth-manager`

也可以把该目录复制到：

`~/.codex/skills/personal-wealth-manager`

安装后可直接描述需求，或使用 `$personal-wealth-manager` 明确调用。

## 使用示例

- “帮我盘点三个平台的基金和证券持仓，先不要建议交易。”
- “这些基金有很多重复，帮我区分核心仓、研究仓和待清理项。”
- “结合我的收入、支出和现金储备，判断我能承担多大的投资回撤。”
- “我现在没有本金，帮我先建立现金流和可投资能力。”

## 设计边界

- 默认只读分析；不会代替用户下单、赎回、转账或连接账户。
- 不索取密码、验证码、完整账号、身份证号、保单号或私钥。
- 不提供默认仓位、买卖时点或保证收益。
- 房产、车辆、配偶资产、保险保障与养老仅在影响流动性、风险或共同决策时作为辅助背景。
- 当前默认中国大陆环境；涉及实时制度或产品规则时，应重新核对官方来源。

## 隐私

本仓库只包含通用说明、脚本与测试，不包含任何真实用户的余额、交易、持仓、账单、截图或身份信息。请勿把真实财务资料提交到公开 Issue 或 Pull Request。详见 [SECURITY.md](SECURITY.md)。

## 验证

```bash
python3 skills/personal-wealth-manager/scripts/test_wealth_math.py
```

## 许可与免责声明

代码与 Skill 内容采用 [MIT License](LICENSE)。本项目是教育与决策支持工具，不构成持牌投资、法律、税务或保险建议。

## 设计参考

- [OpenAI Skills](https://github.com/openai/skills)
- [Agent Skills specification](https://agentskills.io/specification)
