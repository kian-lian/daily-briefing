"""AI 分类总结模块 - GitHub Trending"""

import json
import os
import time

from openai import OpenAI

from src.github_trending import TrendingRepo

SYSTEM_PROMPT = """你是一位资深开源技术观察者，负责将 GitHub Trending 仓库整理成一份高质量的每日简报。

你需要输出以下 4 个部分：

1. **one_liner**: 一句话总览（30-60字），概括今天 trending 集中在哪几类方向。
2. **recommendations**: 今日推荐关注，按领域分组（如 AI/ML、Web 框架、开发工具、编程语言、基础设施等），每个领域选 2-4 个最值得关注的仓库。
3. **descriptions**: 将所有仓库的英文描述翻译为简洁的中文（15-30字），用序号作为 key。
4. **conclusion**: 简短结论（2-3 句话），总结今日 trending 反映的技术趋势。

要求：
- 每个仓库通过其在输入列表中的序号（从 0 开始）引用
- recommendations 中用 repo_indices 数组引用仓库
- descriptions 中为每个仓库提供中文描述，key 为字符串格式的序号
- 语气简洁专业，有洞察力
- 特别关注今日新增 star 数多的项目

严格按以下 JSON 格式输出，不要输出其他内容：
{
  "one_liner": "今天 trending 主要集中在...",
  "recommendations": [
    {
      "direction": "AI/ML",
      "repo_indices": [1, 3, 7]
    }
  ],
  "descriptions": {
    "0": "中文描述...",
    "1": "中文描述..."
  },
  "conclusion": "今天的 trending 说明..."
}"""


def summarize(repos: list[TrendingRepo]) -> dict:
    """调用 LLM 对 trending 仓库进行分类和总结"""
    lines = []
    for i, r in enumerate(repos):
        lines.append(
            f"[{i}] {r.name}\n"
            f"    描述: {r.description}\n"
            f"    语言: {r.language} | ⭐ {r.stars} | 🍴 {r.forks} | 今日 +{r.stars_today}"
        )

    user_content = (
        f"以下是今日 GitHub Trending {len(repos)} 个仓库：\n\n"
        + "\n\n".join(lines)
    )

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ.get("OPENAI_BASE_URL"),
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

    content = response.choices[0].message.content
    if "```" in content:
        content = content.split("```json")[-1].split("```")[0] if "```json" in content else content.split("```")[1].split("```")[0]
    return json.loads(content.strip())


def summarize_with_fallback(repos: list[TrendingRepo]) -> dict | None:
    """带重试和降级的总结，失败返回 None"""
    for attempt in range(3):
        try:
            return summarize(repos)
        except Exception as e:
            print(f"AI 总结失败 (第 {attempt + 1} 次): {e}")
            if attempt < 2:
                time.sleep(5)
    print("AI 总结全部失败，将推送原始列表")
    return None
