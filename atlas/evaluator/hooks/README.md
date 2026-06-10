# Evaluator 证据强制 hooks(注册说明)

三层强制(RESEARCH.md 决策):
1. **subagent tools 白名单**(`.claude/agents/atlas-evaluator.md` frontmatter)
   —— harness 原生强制,C1 已配。
2. **PreToolUse hook**(本目录 `block_non_evidence.py`)—— 白名单外
   调用 exit 2 阻断,belt-and-suspenders。
3. **trace schema 校验**(`atlas.evaluator.validate_trace`)—— 不合
   `verification-trace-1.0.json` 的判决输出直接拒绝。

## hook 注册(需用户批准,不自动改 settings)

在项目 `.claude/settings.json` 加:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "python atlas/evaluator/hooks/block_non_evidence.py"
      }]
    }]
  }
}
```

并在运行 Evaluator 的环境设 `ATLAS_EVALUATOR_HOOK=1`(未设时 hook
直接放行,不影响其它会话)。脚本逻辑有 pytest 覆盖
(`atlas/tests/test_evaluator.py`)。
