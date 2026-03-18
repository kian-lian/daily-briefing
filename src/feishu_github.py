"""飞书 Webhook 推送模块 - GitHub Trending"""

import json
import os
import time
import urllib.request
from datetime import datetime, timezone, timedelta

from src.github_trending import TrendingRepo


def _md(content: str) -> dict:
    return {"tag": "markdown", "content": content}


def _hr() -> dict:
    return {"tag": "hr"}


def _fmt_num(n: str) -> str:
    """格式化数字：>=1000 显示为 1.2k 形式"""
    try:
        v = int(n)
    except (ValueError, TypeError):
        return n
    if v >= 1000:
        return f"{v / 1000:.1f}k".replace(".0k", "k")
    return str(v)


def _build_card(
    repos: list[TrendingRepo],
    summary: dict | None,
) -> dict:
    """构造飞书 Interactive Card 消息体"""
    tz = timezone(timedelta(hours=8))
    date_str = datetime.now(tz).strftime("%Y-%m-%d")

    elements: list[dict] = []

    if summary:
        elements.append(_md(f"**日期：{date_str}**"))
        elements.append(_md(f"**一句话总览**\n{summary.get('one_liner', '')}"))
        elements.append(_hr())

        recommendations = summary.get("recommendations", [])
        descriptions = summary.get("descriptions", {})

        if recommendations:
            elements.append(_md("**今日推荐关注**"))
            for rec in recommendations:
                lines = [f"**{rec['direction']}**"]
                for idx in rec.get("repo_indices", []):
                    if 0 <= idx < len(repos):
                        r = repos[idx]
                        lang_tag = f"`{r.language}`" if r.language != "Unknown" else ""
                        desc = descriptions.get(str(idx), r.description)
                        lines.append(
                            f"• [{r.name}]({r.url}) {lang_tag} "
                            f"⭐{_fmt_num(r.stars)} (+{_fmt_num(r.stars_today)})"
                        )
                        if desc:
                            lines.append(f"  {desc}")
                elements.append(_md("\n".join(lines)))
            elements.append(_hr())

        conclusion = summary.get("conclusion", "")
        if conclusion:
            elements.append(_md(f"**简短结论**\n{conclusion}"))

    else:
        # 降级：无 AI 总结，按顺序列出
        elements.append(_md(f"**日期：{date_str}**\n今日共 {len(repos)} 个仓库上榜"))
        elements.append(_hr())
        for i, r in enumerate(repos):
            lang_tag = f"`{r.language}`" if r.language != "Unknown" else ""
            elements.append(_md(
                f"**#{i + 1} [{r.name}]({r.url})** {lang_tag}\n"
                f"⭐ {_fmt_num(r.stars)} (+{_fmt_num(r.stars_today)} today) · 🍴 {_fmt_num(r.forks)}\n"
                f"{r.description}"
            ))
            if i < len(repos) - 1:
                elements.append(_hr())

    elements.append(_hr())
    elements.append(_md(
        f"📊 共 {len(repos)} 个仓库 · 数据来源 "
        f"[GitHub Trending](https://github.com/trending) · 自动推送"
    ))

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "🐙 GitHub Trending 日报"},
                "template": "purple",
            },
            "elements": elements,
        },
    }


def push_to_feishu(repos: list[TrendingRepo], summary: dict | None) -> None:
    """推送飞书消息，带重试"""
    webhook_url = os.environ["FEISHU_WEBHOOK_URL"]
    card = _build_card(repos, summary)
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
