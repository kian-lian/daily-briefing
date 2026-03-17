"""AI 分类总结模块，使用 GPT-4o-mini"""

import json
import os
import time

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
    lines = []
    for i, a in enumerate(articles):
        lines.append(
            f"[{i}] {a.title}\n"
            f"    摘要: {a.brief}\n"
            f"    热度: 👍{a.digg_count} 👀{a.view_count}"
        )

    user_content = (
        f"以下是今日掘金热榜 {len(articles)} 篇文章：\n\n"
        + "\n\n".join(lines)
    )

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ.get("OPENAI_BASE_URL"),  # 可选，兼容第三方 API
    )
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    response = client.chat.completions.create(
        model=model,
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
                time.sleep(5)
    print("AI 总结全部失败，将推送原始列表")
    return None
