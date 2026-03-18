# daily-briefing

每天自动抓取掘金热榜 Top 50 和 GitHub Trending Top 25，AI 分类总结后推送飞书简报。

## 配置

1. 复制 `.env.example` 为 `.env`，填入密钥
2. GitHub 仓库 Settings → Secrets 添加 `OPENAI_API_KEY` 和 `FEISHU_WEBHOOK_URL`

## 本地运行

```bash
pip install -r requirements.txt

# 掘金热榜简报
python -m src.main

# GitHub Trending 日报
python -m src.main_github
```

## 自动推送

GitHub Actions 通过 `workflow_dispatch` 触发，由外部 cron-job.org 定时调用。
两个简报（掘金热榜、GitHub Trending）作为独立 job 并行执行。
也可在 Actions 页面手动触发。
