# daily-briefing

每天中午自动抓取掘金热榜 Top 50，AI 分类总结后推送飞书简报。

## 配置

1. 复制 `.env.example` 为 `.env`，填入密钥
2. GitHub 仓库 Settings → Secrets 添加 `OPENAI_API_KEY` 和 `FEISHU_WEBHOOK_URL`

## 本地运行

```bash
pip install -r requirements.txt
python -m src.main
```

## 自动推送

GitHub Actions 每天 UTC 04:00（北京 12:00）自动执行。
也可在 Actions 页面手动触发。
