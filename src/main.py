"""入口：串联抓取 → 总结 → 推送"""

from dotenv import load_dotenv
load_dotenv()  # 加载 .env 文件到环境变量

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
        print(f"\n    📌 一句话总览: {summary.get('one_liner', '')}")

        recs = summary.get("recommendations", [])
        if recs:
            print("\n    📖 今日推荐阅读:")
            for rec in recs:
                print(f"\n    {rec['direction']}")
                for idx in rec.get("article_indices", []):
                    if 0 <= idx < len(articles):
                        a = articles[idx]
                        print(f"       • {a.title}")
                        print(f"         {a.url}")

        conclusion = summary.get("conclusion", "")
        if conclusion:
            print(f"\n    💡 简短结论: {conclusion}")
        print()
    else:
        print("    跳过 AI 总结，使用原始列表")

    print("3/3 推送飞书...")
    push_to_feishu(articles, summary)
    print("=== 完成 ===")


if __name__ == "__main__":
    main()
