# 智能乐器 & 传统乐器跨平台市场调研

横向对比 Amazon、eBay、Walmart、TikTok Shop、Temu 五个平台上 55 个子品类（11 个大类）乐器的价格、销量代理指标、用户评论。

## 快速开始

```bash
# 1. 安装依赖
pip3 install -r requirements.txt
playwright install chromium

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 ANTHROPIC_API_KEY 等

# 3. 跑单平台单品类（验证）
python3 main.py --platform amazon --category smart_guitar --top-n 10

# 4. 跑全量
python3 main.py --all
```

## 品类总览

共 55 个子品类，按 11 个大类组织：

| 大类 | 子品类 |
| --- | --- |
| 传统弦乐器（拨弦） | guitar、electric_guitar、bass_guitar、ukulele、harp、mandolin、banjo |
| 传统弦乐器（弓弦） | violin、cello、viola、double_bass |
| 键盘 / 击弦 | acoustic_piano、digital_piano、hammered_dulcimer |
| 木管 | flute、clarinet、oboe、saxophone |
| 铜管 | trumpet、trombone、french_horn |
| 打击（体鸣 + 膜鸣） | marimba、xylophone、gong、cymbals、acoustic_drum、djembe、cajon、timpani |
| 中国传统乐器 | guzheng、guqin、pipa、erhu、dizi、hulusi、suona、yangqin |
| 世界民族乐器 | morin_khuur、sitar、tabla、shamisen、oud、didgeridoo |
| 现代电子 / MIDI | synthesizer、electronic_drum、electronic_keyboard、drum_pad、midi_keyboard、launchpad、midi_guitar |
| 电声 / 静音 | electric_violin、silent_piano |
| 智能乐器 | smart_guitar、smart_piano、smart_drum |

完整定义见 [config/keywords.py](config/keywords.py)。

## 数据字典

### 公开数据（真实）
- 价格、原价、货币
- 评分、评论数、评论文本
- 标题、品牌、卖家
- Amazon BSR 排名（推算销量量级）
- Temu/TikTok Shop 显示的「已售 N+ 件」

### 代理估算指标（标注为 estimated）
- 销量：评论数 × 1.5-3% 系数（行业经验值）
- 上架时长：从最早评论日期推算

### 拿不到的指标
- 点击率（CTR）—— 平台商家后台数据
- 用户国家分布 —— 平台内部数据
- 精确成交单数（除 Temu/TikTok Shop 外）

## 输出

- `data/processed/products_master.xlsx` — 全部商品
- `data/processed/reviews_master.xlsx` — 全部评论
- `data/processed/insights_report.md` — AI 市场洞察
- `data/processed/charts/` — Plotly 交互图
