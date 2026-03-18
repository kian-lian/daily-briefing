"""入口：GitHub Trending 每日简报"""

from dotenv import load_dotenv
load_dotenv()

from src.github_trending import fetch_trending
from src.summarizer_github import summarize_with_fallback
from src.feishu_github import push_to_feishu


def main():
    print("=== GitHub Trending 日报 ===")

    print("1/3 抓取 GitHub Trending...")
    repos = fetch_trending(25)
    print(f"    获取到 {len(repos)} 个仓库")

    if not repos:
        print("未获取到仓库，终止")
        return

    print("2/3 AI 分类总结...")
    summary = summarize_with_fallback(repos)
    if summary:
        print(f"\n    📌 一句话总览: {summary.get('one_liner', '')}")

        recs = summary.get("recommendations", [])
        if recs:
            print("\n    📖 今日推荐关注:")
            for rec in recs:
                print(f"\n    {rec['direction']}")
                for idx in rec.get("repo_indices", []):
                    if 0 <= idx < len(repos):
                        r = repos[idx]
                        print(f"       • {r.name} ⭐{r.stars} (+{r.stars_today})")

        conclusion = summary.get("conclusion", "")
        if conclusion:
            print(f"\n    💡 简短结论: {conclusion}")
        print()
    else:
        print("    跳过 AI 总结，使用原始列表")

    print("3/3 推送飞书...")
    push_to_feishu(repos, summary)
    print("=== 完成 ===")


if __name__ == "__main__":
    main()
