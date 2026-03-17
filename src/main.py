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
