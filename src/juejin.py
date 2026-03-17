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
