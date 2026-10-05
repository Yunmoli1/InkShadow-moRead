"""任务失败错误分类码（A2）。

分类依据：工具退出码 + 日志尾部/异常文本的关键字。
前端用 ERROR_LABELS / ERROR_SUGGESTIONS 把码翻译成中文与建议动作。
"""
from __future__ import annotations

import re

# 分类码 → 中文标签 / 建议动作
ERROR_LABELS: dict[str, str] = {
    "TOOL_NOT_FOUND": "工具未安装",
    "SPAWN_ERROR": "工具启动失败",
    "NETWORK_ERROR": "网络错误",
    "AUTH_REQUIRED": "站点需要登录",
    "NO_CONTENT": "未获取到有效内容",
    "TIMEOUT": "任务超时",
    "QUOTA_EXCEEDED": "存储配额不足",
    "IMPORT_ERROR": "导入失败",
    "INTERNAL_ERROR": "内部错误",
    "UNKNOWN": "未知错误",
}

ERROR_SUGGESTIONS: dict[str, str] = {
    "TOOL_NOT_FOUND": "到工具箱页按提示安装该工具，或手动指定其他工具重试",
    "SPAWN_ERROR": "确认工具可执行（在工具箱重新检测版本），或重装后重试",
    "NETWORK_ERROR": "检查本机网络，或在设置中配置代理后重试",
    "AUTH_REQUIRED": "该站点可能需要登录/受保护，可尝试换源或其他工具",
    "NO_CONTENT": "站点结构可能已变化或不支持，试试「一键换源」或换工具",
    "TIMEOUT": "任务超时被终止；可重试，若反复超时请检查网络或更换工具",
    "QUOTA_EXCEEDED": "清理存储空间或调大设置中的存储配额",
    "IMPORT_ERROR": "产物可能损坏；查看任务日志，或重试",
    "INTERNAL_ERROR": "查看结构化日志（data/logs/moread.log）定位原因",
    "UNKNOWN": "查看任务日志中的最近输出定位原因",
}

_AUTH_PAT = re.compile(
    r"401|403|unauthorized|forbidden|login required|sign ?in required|"
    r"authentication|需要登录|请登录|鉴权|cookies? (expired|required)", re.I)
_NET_PAT = re.compile(
    r"timeout|timed out|getaddrinfo|name or service not known|err_name_not_resolved|"
    r"connection ?(refused|reset|error)|connect(ion)? ?error|all connection attempts failed|"
    r"network is unreachable|temporary failure in name resolution|"
    r"ssl|tls|handshake|无法连接|网络错误|积极拒绝|连接被拒绝|连接已重置|连接超时|"
    r"winerror ?(10060|10061|10054|11001)|errno ?(-2|-3|111)", re.I)
_QUOTA_PAT = re.compile(r"no space left|disk full|quota exceeded|配额|存储空间不足", re.I)
_NOCONTENT_PAT = re.compile(r"404|not found|未找到|不存在|no valid", re.I)
_SPAWN_PAT = re.compile(
    r"is not recognized|no such file or directory|permission denied|拒绝访问|"
    r"cannot find the (path|file)|os ?error ?(2|5|13)", re.I)


def classify_text(text: str) -> str:
    """从异常/日志文本推断错误码（无退出码场景，如内置下载器）。"""
    if not text:
        return "UNKNOWN"
    if _AUTH_PAT.search(text):
        return "AUTH_REQUIRED"
    if _NET_PAT.search(text):
        return "NETWORK_ERROR"
    if _QUOTA_PAT.search(text):
        return "QUOTA_EXCEEDED"
    if _NOCONTENT_PAT.search(text):
        return "NO_CONTENT"
    if _SPAWN_PAT.search(text):
        return "SPAWN_ERROR"
    return "UNKNOWN"


def classify_failure(rc: int, tail: str = "") -> str:
    """按工具退出码 + 日志尾部分类失败原因。"""
    if rc == 0:
        return ""
    return classify_text(tail)
