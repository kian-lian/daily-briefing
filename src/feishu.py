"""飞书 Webhook 推送模块"""

import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone, timedelta

from src.juejin import Article


def _md(content: str) -> dict:
    """快捷构造 markdown 元素"""
    return {"tag": "markdown", "content": content}


def _hr() -> dict:
    return {"tag": "hr"}


def _linkify_refs(text: str, articles: list[Article]) -> str:
    """将文本中的 [序号] 替换为飞书可点击链接 [[序号]](url)"""
    def _replace(m: re.Match) -> str:
        idx = int(m.group(1))
        if 0 <= idx < len(articles):
            return f"[[{idx}]]({articles[idx].url})"
        return m.group(0)
    return re.sub(r"\[(\d+)\]", _replace, text)


def _build_card(
    articles: list[Article],
    summary: dict | None,
) -> dict:
    """构造飞书 Interactive Card 消息体"""
    tz = timezone(timedelta(hours=8))
    date_str = datetime.now(tz).strftime("%Y-%m-%d")

    elements: list[dict] = []

    if summary:
        # 日期 + 一句话总览
        elements.append(_md(f"**日期：{date_str}**"))
        elements.append(_md(f"**一句话总览**\n{summary.get('one_liner', '')}"))
        elements.append(_hr())

        # 今日推荐阅读
        recommendations = summary.get("recommendations", [])
        if recommendations:
            elements.append(_md("**今日推荐阅读**"))
            for rec in recommendations:
                lines = [f"**{rec['direction']}**"]
                for idx in rec.get("article_indices", []):
                    if 0 <= idx < len(articles):
                        a = articles[idx]
                        lines.append(f"• [{a.title}]({a.url})")
                elements.append(_md("\n".join(lines)))
            elements.append(_hr())

        # 简短结论
        conclusion = summary.get("conclusion", "")
        if conclusion:
            elements.append(_md(f"**简短结论**\n{conclusion}"))

    else:
        # 降级：无 AI 总结，按顺序列出
        elements.append(_md(f"**日期：{date_str}**\n今日共 {len(articles)} 篇文章上榜"))
        elements.append(_hr())
        for i, a in enumerate(articles):
            elements.append(_md(
                f"**第{i + 1}名 | [{a.title}]({a.url})**\n"
                f"👍 {a.digg_count}赞 · 👀 {a.view_count}阅读 · 💬 {a.comment_count}评论\n"
                f"{a.brief}"
            ))
            elements.append(_hr())

    # 底部
    elements.append(_md(
        f"📊 共 {len(articles)} 篇 · 数据来源 [掘金](https://juejin.cn) · 自动推送"
    ))

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "📰 今日掘金热榜简报"},
                "template": "blue",
            },
            "elements": elements,
        },
    }


def push_to_feishu(articles: list[Article], summary: dict | None) -> None:
    """推送飞书消息，带重试"""
    webhook_url = os.environ["FEISHU_WEBHOOK_URL"]
    card = _build_card(articles, summary)
    payload = json.dumps(card).encode()

    for attempt in range(3):
        try:
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                print("飞书推送成功")
                return
            raise RuntimeError(f"飞书返回错误: {result}")
        except Exception as e:
            print(f"飞书推送失败 (第 {attempt + 1} 次): {e}")
            if attempt < 2:
                time.sleep(5)
            else:
                raise
