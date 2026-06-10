"""C2:PreToolUse hook —— Evaluator 证据纪律的 harness 层强制。

注册(用户 settings.json 或项目 .claude/settings.json,见 README.md):
PreToolUse hook,matcher 针对 Task(subagent atlas-evaluator)会话,
或全局注册后凭 ATLAS_EVALUATOR_HOOK=1 环境变量启用。

协议:stdin 收 JSON {tool_name, tool_input,...};exit 2 = 阻断
(stderr 给模型),exit 0 = 放行。
"""
import json
import os
import sys

ALLOWED = {'Bash', 'Read', 'Grep', 'Glob'}
BLOCKED_ALWAYS = {'WebFetch', 'WebSearch', 'AskUserQuestion', 'Skill',
                  'Write', 'Edit', 'NotebookEdit', 'Agent', 'Task'}


def main():
    if os.environ.get('ATLAS_EVALUATOR_HOOK') != '1':
        return 0  # 未启用,放行
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool = payload.get('tool_name', '')
    if tool in BLOCKED_ALWAYS or (tool and tool not in ALLOWED
                                  and not tool.startswith('mcp__atlas')):
        sys.stderr.write(
            f'[ATLAS Evaluator 证据纪律] 工具 {tool} 不在证据白名单 '
            f'{sorted(ALLOWED)} + mcp__atlas* 内,已阻断;'
            f'Evaluator 只认仓内工具证据')
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
