# 手术显微镜招投标信息爬虫

自动爬取招投标网站，生成每日手术显微镜相关招投标信息汇总报告。

## 数据源

1. **必联网/采招网** (bidcenter.com.cn) - 第一信源
2. **中国国际招标网** (chinabidding.com) - 第二信源
3. **中国政府采购网** (ccgp.gov.cn) - 补充信源

## 报告格式

Markdown 格式，按信息类型分类：
- 招标信息（详细表格）
- 预采购信息（简略通知）
- 调研信息（简略通知）
- 中标信息（简略通知）
- 变更信息（简略通知）

## 本地运行

```bash
pip install playwright
python -m playwright install chromium

# 设置环境变量
export BIDCENTER_USERNAME="your_username"
export BIDCENTER_PASSWORD="your_password"
export CHINABIDDING_USERNAME="your_username"
export CHINABIDDING_PASSWORD="your_password"

python bidding_scraper.py
```

## GitHub Actions

报告每天早上9点（北京时间）自动生成。
