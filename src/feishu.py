"""飞书 Webhook 推送模块"""

import json
import os
import time
import urllib.request
from datetime import datetime, timezone, timedelta

from src.juejin import Article


def _build_card(
    articles: list[Article],
    summary: dict | None,
) -> dict:
    """构造飞书 Interactive Card 消息体"""
    tz = timezone(timedelta(hours=8))
    date_str = datetime.now(tz).strftime("%Y-%m-%d")

    elements: list[dict] = []

    if summary:
        # 一句话总览
        elements.append({
            "tag": "markdown",
            "content": f"**{summary['one_liner']}**",
        })
        elements.append({"tag": "hr"})

        # 今日最热
        top = summary.get("top_pick", {})
        top_idx = top.get("index", 0)
        if 0 <= top_idx < len(articles):
            a = articles[top_idx]
            elements.append({
                "tag": "markdown",
                "content": (
                    f"🔥 **今日最热**\n"
                    f"[{a.title}]({a.url})\n"
                    f"👤 {a.author} · 👍{a.digg_count} · 👀{a.view_count}\n"
                    f"_{top.get('reason', '')}_"
                ),
            })
            elements.append({"tag": "hr"})

        # 分类板块
        for cat in summary.get("categories", []):
            lines = [f"**{cat['name']}** — {cat['summary']}"]
            for idx in cat.get("article_indices", []):
                if 0 <= idx < len(articles):
                    a = articles[idx]
                    lines.append(
                        f"• [{a.title}]({a.url})  "
                        f"👤{a.author} 👍{a.digg_count} 👀{a.view_count}"
                    )
            elements.append({"tag": "markdown", "content": "\n".join(lines)})
    else:
        # 降级：无 AI 总结，直接列出文章
        for i, a in enumerate(articles):
            elements.append({
                "tag": "markdown",
                "content": (
                    f"**{i + 1}.** [{a.title}]({a.url})\n"
                    f"👤 {a.author} · 👍{a.digg_count} · 👀{a.view_count}"
                ),
            })

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "markdown",
        "content": f"📊 共 {len(articles)} 篇 · 数据来源 [掘金](https://juejin.cn) · 自动推送",
    })

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"📰 掘金热榜简报 | {date_str}"},
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
