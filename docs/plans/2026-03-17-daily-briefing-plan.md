# daily-briefing 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 创建一个 GitHub Actions 定时服务，每天中午抓取掘金热榜 Top 50，通过 GPT-4o-mini 分类总结后推送飞书富文本卡片。

**Architecture:** 单仓库 Python 脚本，4 个模块各司其职（抓取 → AI 总结 → 飞书推送 → 入口串联），GitHub Actions cron 调度，Secrets 管理密钥。

**Tech Stack:** Python 3.12, OpenAI API (GPT-4o-mini), 飞书 Webhook, GitHub Actions

---

### Task 1: 项目初始化

**Files:**
- Create: `/Users/lian/dev/my-projects/daily-briefing/.gitignore`
- Create: `/Users/lian/dev/my-projects/daily-briefing/.env.example`
- Create: `/Users/lian/dev/my-projects/daily-briefing/requirements.txt`
- Create: `/Users/lian/dev/my-projects/daily-briefing/README.md`
- Create: `/Users/lian/dev/my-projects/daily-briefing/src/__init__.py`

**Step 1: 创建项目目录和文件**

`.gitignore`:
```
__pycache__/
*.pyc
.env
.venv/
```

`.env.example`:
```
OPENAI_API_KEY=sk-your-key-here
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your-token
```

`requirements.txt`:
```
openai>=1.0.0
```

`README.md`:
```markdown
# daily-briefing

每天中午自动抓取掘金热榜 Top 50，AI 分类总结后推送飞书简报。

## 配置

1. 复制 `.env.example` 为 `.env`，填入密钥
2. GitHub 仓库 Settings → Secrets 添加 `OPENAI_API_KEY` 和 `FEISHU_WEBHOOK_URL`

## 本地运行

pip install -r requirements.txt
python src/main.py

## 自动推送

GitHub Actions 每天 UTC 04:00（北京 12:00）自动执行。
也可在 Actions 页面手动触发。
```

`src/__init__.py`: 空文件

**Step 2: 初始化 Git 仓库**

```bash
cd /Users/lian/dev/my-projects/daily-briefing
git init
git add .
git commit -m "chore: 初始化项目结构"
```

---

### Task 2: 掘金抓取模块

**Files:**
- Create: `src/juejin.py`

**Step 1: 实现抓取逻辑**

```python
"""掘金热榜抓取模块"""

import json
import time
import urllib.request
from dataclasses import dataclass


@dataclass
class Article:
    """热榜文章数据"""
    title: str
    url: str
    author: str
    digg_count: int
    view_count: int
    comment_count: int
    collect_count: int
    brief: str


API_URL = "https://api.juejin.cn/recommend_api/v1/article/recommend_all_feed"


def fetch_hot_list(target: int = 50) -> list[Article]:
    """抓取掘金热榜，去重后返回目标数量的文章"""
    seen_ids: set[str] = set()
    articles: list[Article] = []
    cursor = "0"
    max_retries = 3

    while len(articles) < target:
        payload = json.dumps({
            "id_type": 2,
            "sort_type": 3,
            "cursor": cursor,
            "limit": target,
        }).encode()

        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    API_URL,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                break
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(5)
                else:
                    raise

        items = data.get("data", [])
        if not items:
            break

        new_count = 0
        for item in items:
            info = item.get("item_info", {})
            article_info = info.get("article_info", {})
            author_info = info.get("author_user_info", {})
            aid = article_info.get("article_id", "")

            if not aid or aid in seen_ids:
                continue
            seen_ids.add(aid)
            new_count += 1

            articles.append(Article(
                title=article_info.get("title", ""),
                url=f"https://juejin.cn/post/{aid}",
                author=author_info.get("user_name", ""),
                digg_count=article_info.get("digg_count", 0),
                view_count=article_info.get("view_count", 0),
                comment_count=article_info.get("comment_count", 0),
                collect_count=article_info.get("collect_count", 0),
                brief=article_info.get("brief_content", "")[:80],
            ))

        # 没有新文章了，停止翻页
        if new_count == 0:
            break
        cursor = str(len(seen_ids))

    return articles[:target]
```

**Step 2: 本地验证**

```bash
cd /Users/lian/dev/my-projects/daily-briefing
python -c "from src.juejin import fetch_hot_list; arts = fetch_hot_list(5); print(f'{len(arts)} articles'); print(arts[0].title)"
```

Expected: 输出 5 篇文章标题

**Step 3: Commit**

```bash
git add src/juejin.py
git commit -m "feat: 添加掘金热榜抓取模块"
```

---

### Task 3: AI 总结模块

**Files:**
- Create: `src/summarizer.py`

**Step 1: 实现 AI 分类总结**

```python
"""AI 分类总结模块，使用 GPT-4o-mini"""

import json
import os

from openai import OpenAI

from src.juejin import Article

SYSTEM_PROMPT = """你是一位技术媒体编辑，负责将掘金热榜文章分类整理成简报。

要求：
1. 将文章分为 4-6 个主题类别（如：AI 与大模型、前端工程、后端与架构、移动开发、开发工具、行业热点等）
2. 每个类别给出一句话趋势总结（15-30字）
3. 从所有文章中选出 1 篇"今日最热"，写一句推荐语（20-40字）
4. 写一句今日热榜总览（20-40字）
5. 每篇文章只能属于一个类别
6. 类别按文章数量从多到少排序

严格按以下 JSON 格式输出，不要输出其他内容：
{
  "top_pick": {"index": 0, "reason": "推荐理由"},
  "categories": [
    {
      "name": "类别名",
      "summary": "趋势总结",
      "article_indices": [0, 3, 7]
    }
  ],
  "one_liner": "今日热榜一句话总览"
}

其中 index / article_indices 是文章在输入列表中的序号（从 0 开始）。"""


def summarize(articles: list[Article]) -> dict:
    """调用 GPT-4o-mini 对文章列表进行分类和总结"""
    # 构造输入文本
    lines = []
    for i, a in enumerate(articles):
        lines.append(f"[{i}] {a.title}\n    摘要: {a.brief}\n    热度: 👍{a.digg_count} 👀{a.view_count}")

    user_content = f"以下是今日掘金热榜 {len(articles)} 篇文章：\n\n" + "\n\n".join(lines)

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    return json.loads(response.choices[0].message.content)


def summarize_with_fallback(articles: list[Article]) -> dict | None:
    """带重试和降级的总结，失败返回 None"""
    for attempt in range(3):
        try:
            return summarize(articles)
        except Exception as e:
            print(f"AI 总结失败 (第 {attempt + 1} 次): {e}")
            if attempt < 2:
                import time
                time.sleep(5)
    print("AI 总结全部失败，将推送原始列表")
    return None
```

**Step 2: 本地验证（需要 OPENAI_API_KEY）**

```bash
cd /Users/lian/dev/my-projects/daily-briefing
OPENAI_API_KEY=sk-xxx python -c "
from src.juejin import fetch_hot_list
from src.summarizer import summarize
arts = fetch_hot_list(10)
result = summarize(arts)
import json; print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

**Step 3: Commit**

```bash
git add src/summarizer.py
git commit -m "feat: 添加 AI 分类总结模块"
```

---

### Task 4: 飞书推送模块

**Files:**
- Create: `src/feishu.py`

**Step 1: 实现飞书卡片构造和推送**

```python
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
```

**Step 2: Commit**

```bash
git add src/feishu.py
git commit -m "feat: 添加飞书 Webhook 推送模块"
```

---

### Task 5: 主入口

**Files:**
- Create: `src/main.py`

**Step 1: 实现主流程**

```python
"""入口：串联抓取 → 总结 → 推送"""

from src.juejin import fetch_hot_list
from src.summarizer import summarize_with_fallback
from src.feishu import push_to_feishu


def main():
    print("=== 掘金热榜简报 ===")

    print("1/3 抓取掘金热榜...")
    articles = fetch_hot_list(50)
    print(f"    获取到 {len(articles)} 篇文章")

    if not articles:
        print("未获取到文章，终止")
        return

    print("2/3 AI 分类总结...")
    summary = summarize_with_fallback(articles)
    if summary:
        cats = summary.get("categories", [])
        print(f"    分为 {len(cats)} 个类别")
    else:
        print("    跳过 AI 总结，使用原始列表")

    print("3/3 推送飞书...")
    push_to_feishu(articles, summary)
    print("=== 完成 ===")


if __name__ == "__main__":
    main()
```

**Step 2: 本地端到端测试**

```bash
cd /Users/lian/dev/my-projects/daily-briefing
export OPENAI_API_KEY=sk-xxx
export FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
python -m src.main
```

**Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat: 添加主入口串联流程"
```

---

### Task 6: GitHub Actions 工作流

**Files:**
- Create: `.github/workflows/briefing.yml`

**Step 1: 创建 workflow 文件**

```yaml
name: 掘金热榜简报

on:
  schedule:
    # UTC 04:00 = 北京时间 12:00
    - cron: '0 4 * * *'
  workflow_dispatch:

jobs:
  briefing:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: 安装依赖
        run: pip install -r requirements.txt

      - name: 运行简报推送
        run: python -m src.main
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}
```

**Step 2: Commit**

```bash
git add .github/workflows/briefing.yml
git commit -m "ci: 添加 GitHub Actions 定时推送工作流"
```

---

### Task 7: 推送远程仓库

**Step 1: 在 GitHub 创建仓库并推送**

```bash
cd /Users/lian/dev/my-projects/daily-briefing
gh repo create kian-lian/daily-briefing --private --source=. --push
```

**Step 2: 配置 Secrets**

```bash
gh secret set OPENAI_API_KEY
gh secret set FEISHU_WEBHOOK_URL
```

**Step 3: 手动触发测试**

```bash
gh workflow run briefing.yml
gh run watch
```
