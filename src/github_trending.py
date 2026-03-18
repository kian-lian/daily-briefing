"""GitHub Trending 抓取模块（解析 HTML 页面）"""

import re
import time
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass
class TrendingRepo:
    """Trending 仓库数据"""
    name: str          # owner/repo
    url: str
    description: str
    language: str
    stars: str         # 总 star 数
    forks: str         # 总 fork 数
    stars_today: str   # 今日新增 star


TRENDING_URL = "https://github.com/trending?since=daily"


class _TrendingParser(HTMLParser):
    """解析 GitHub Trending 页面 HTML

    页面结构（每个仓库是一个 article.Box-row）:
      <article class="Box-row">
        <h2> <a href="/owner/repo"> owner / repo </a> </h2>
        <p class="col-9 ..."> description </p>
        <span class="d-inline-block ml-0 ..."> language </span>
        <a href="/owner/repo/stargazers"> 12,345 </a>
        <a href="/owner/repo/forks"> 1,234 </a>
        <span class="d-inline-block float-sm-right"> 567 stars today </span>
      </article>
    """

    def __init__(self):
        super().__init__()
        self.repos: list[dict] = []
        self._cur: dict = {}
        self._in_article = False
        self._state = ""      # 当前捕获状态
        self._buf = ""        # 文本缓冲

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        cls = attr.get("class", "")

        # 进入一个仓库块
        if tag == "article" and "Box-row" in cls:
            self._in_article = True
            self._cur = dict(name="", url="", description="", language="",
                             stars="", forks="", stars_today="")
            return

        if not self._in_article:
            return

        # 仓库名: <h2 ...> <a href="/owner/repo">
        if tag == "h2":
            self._state = "h2"
        if self._state == "h2" and tag == "a":
            href = attr.get("href", "")
            self._cur["url"] = f"https://github.com{href}"
            self._cur["name"] = href.strip("/")
            self._state = "repo_name"
            self._buf = ""

        # 描述: <p class="col-9 ...">
        if tag == "p" and "col-9" in cls:
            self._state = "desc"
            self._buf = ""

        # 编程语言: <span itemprop="programmingLanguage">
        if tag == "span" and attr.get("itemprop") == "programmingLanguage":
            self._state = "lang"
            self._buf = ""

        # stars / forks: <a class="... Link--muted d-inline-block ..." href="...">
        if tag == "a" and ("Link--muted" in cls or "muted-link" in cls) and "d-inline-block" in cls:
            href = attr.get("href", "")
            if "/stargazers" in href:
                self._state = "stars"
                self._buf = ""
            elif "/forks" in href or "/network" in href:
                self._state = "forks"
                self._buf = ""

        # 今日 star: <span class="d-inline-block float-sm-right">
        if tag == "span" and "d-inline-block" in cls and "float-sm-right" in cls:
            self._state = "today"
            self._buf = ""

    def handle_endtag(self, tag):
        if tag == "article" and self._in_article:
            self._in_article = False
            if self._cur.get("name"):
                self.repos.append(self._cur)
            self._cur = {}
            self._state = ""
            return

        if self._state == "repo_name" and tag == "a":
            self._state = ""
        elif self._state == "desc" and tag == "p":
            self._cur["description"] = self._buf.strip()
            self._state = ""
        elif self._state == "lang" and tag == "span":
            self._cur["language"] = self._buf.strip()
            self._state = ""
        elif self._state == "stars" and tag == "a":
            self._cur["stars"] = self._buf.strip().replace(",", "")
            self._state = ""
        elif self._state == "forks" and tag == "a":
            self._cur["forks"] = self._buf.strip().replace(",", "")
            self._state = ""
        elif self._state == "today" and tag == "span":
            text = self._buf.strip()
            m = re.search(r"([\d,]+)\s+stars?\s+today", text)
            self._cur["stars_today"] = m.group(1).replace(",", "") if m else ""
            self._state = ""

    def handle_data(self, data):
        if self._state in ("desc", "lang", "stars", "forks", "today"):
            self._buf += data


def fetch_trending(target: int = 25) -> list[TrendingRepo]:
    """抓取 GitHub Trending 页面，返回仓库列表"""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                TRENDING_URL,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; daily-briefing-bot)",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "identity",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8")
            break
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                raise

    parser = _TrendingParser()
    parser.feed(html)

    if not parser.repos:
        raise RuntimeError("Trending 解析结果为空，疑似页面结构变更或被拦截")

    repos = []
    for item in parser.repos[:target]:
        repos.append(TrendingRepo(
            name=item["name"],
            url=item["url"],
            description=item["description"],
            language=item["language"] or "Unknown",
            stars=item["stars"] or "0",
            forks=item["forks"] or "0",
            stars_today=item["stars_today"] or "0",
        ))

    return repos
