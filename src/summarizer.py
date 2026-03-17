"""AI 分类总结模块，使用 GPT-4o-mini"""

import json
import os
import time

from openai import OpenAI

from src.juejin import Article

SYSTEM_PROMPT = """你是一位资深技术媒体编辑，负责将掘金热榜文章整理成一份高质量的每日简报。

你需要输出以下 3 个部分：

1. **one_liner**: 一句话总览（30-60字），概括今天热榜集中在哪几类话题。
2. **recommendations**: 今日推荐阅读，按方向分组（如 AI 方向、前端方向、移动端方向、后端方向等），每个方向选 2-4 篇最值得读的文章。
3. **conclusion**: 简短结论（2-3 句话），总结今日热榜反映的技术趋势。

要求：
- 每篇文章通过其在输入列表中的序号（从 0 开始）引用
- recommendations 中用 article_indices 数组引用文章
- 语气简洁专业，不要浮夸
- 描述要有洞察，不要只是复述标题

严格按以下 JSON 格式输出，不要输出其他内容：
{
  "one_liner": "今天热榜主要集中在...",
  "recommendations": [
    {
      "direction": "AI 方向",
      "article_indices": [1, 3, 7]
    }
  ],
  "conclusion": "今天的热榜说明..."
}"""


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
    )

    # 兼容不同 API 返回格式
    content = response.choices[0].message.content
    # 提取 JSON（有些模型会在 JSON 外包裹 markdown 代码块）
    if "```" in content:
        content = content.split("```json")[-1].split("```")[0] if "```json" in content else content.split("```")[1].split("```")[0]
    return json.loads(content.strip())


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
