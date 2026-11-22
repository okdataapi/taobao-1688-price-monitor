# taobao-1688-price-monitor: track China e-commerce prices on Taobao, 1688, Xianyu and Douyin Shop

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/okdataapi/taobao-1688-price-monitor/blob/main/price_monitor.ipynb) [中文说明](#中文说明)

What does a camping lantern cost at a 1688 factory, in a Taobao shop, second-hand on Xianyu and in a Douyin Shop?
Give this script a product keyword such as `露营灯` (camping lantern) or `保温杯` (insulated cup). It searches the
platforms you pick, writes every product's price and sales to a CSV, and prints the lowest, median and highest
price on each platform, plus how many times the 1688 wholesale median the Taobao retail median is. Add product IDs
to follow particular listings. Run it every day and the report also lists the biggest price drops and the products
that are new since the last run.

One Python file, standard library only. No Taobao, 1688 or Douyin account, no Chinese phone number, no cookies, no
browser automation: the data comes from the [okdata](https://okdata.online/?src=gh-taobao-1688-price-monitor) API. A search page costs $0.022 on 1688
and Xianyu, $0.043 on Taobao and $0.054 on Douyin Shop; the default run (one keyword on Taobao and 1688) is $0.065. To
try it in the browser first, open the Colab notebook (badge above): it asks for your key, takes a snapshot and charts
the prices by platform.

Good for: cross-border sellers who check 1688 factory prices against Taobao retail before they source, brands
watching what their category sells for in China, sourcing agents and researchers building a price series, and
developers who want to give an AI agent live prices from Chinese marketplaces.

## What you get

<!-- example:start -->
The real report from the second of two runs an hour apart on 2026-11-22: one keyword, `露营灯` (camping lantern),
on all four platforms, plus a Tmall thermos and a 1688 thermos offer followed by ID. Each run made 6 calls and cost
$0.196. Progress lines on stderr are left out, and Xianyu sellers, who are private people, are replaced with
`seller_a`….

```console
$ python3 monitor.py --keyword 露营灯 --platforms all --track taobao:827389194551 --track 1688:594208233163
China e-commerce price monitor 2026-11-22T07:41:59Z (previous run 2026-11-22T06:39:36Z)

Prices for 露营灯, in yuan:
  platform     items    lowest    median   highest
  Taobao          10      6.90     26.30     36.79
  1688            20      1.05      3.93     27.00
  Xianyu          10      9.00     22.00    210.00
  Douyin Shop     30      4.99     19.33    159.99
  Taobao median is 6.7x the 1688 median.

Tracked products:
  ¥99.90 · Taobao · 苏泊尔餐饮具旗舰店 · was ¥99.90 · 苏泊尔保温杯316L不锈钢高颜值男女学生儿童便携泡茶水杯
    https://detail.tmall.com/item.htm?id=827389194551
  ¥8.11 · 1688 · 浙江天诺工贸有限公司 · was ¥8.11, 579,665 sold · 不锈钢保温杯316智能水杯男女士茶水分离高颜值礼品定制杯子批发
    https://detail.1688.com/offer/594208233163.html

Biggest price drops since the last run:
  Of 52 products seen before: 0 cheaper, 0 dearer, 52 unchanged.
  No price went down.

New in the search results, never seen before: 20
  ¥158.00 · Xianyu · seller_h · 铁锚牌老汽灯，带原包装箱，成色还可以，有点年代感，收藏、摆件 都很合适…
    https://www.goofish.com/item?id=1013583230890
  ¥38.00 · Douyin Shop · 暗月官方旗舰店 · 暗月强光手电筒变焦超亮激光户外可充电远射便捷多功能耐用长续航
    https://haohuo.jinritemai.com/ecommerce/trade/detail/index.html?id=3665820867289547181&origin_type=2631
  ¥210.00 · Xianyu · seller_i · 科乐曼 悬挂式E灯 金属绿 2206770 日本代购 49928261…
    https://www.goofish.com/item?id=1077106890045
  ¥29.90 · Douyin Shop · 超星捷个护工厂店 · 可充电小吊扇学生宿舍床上蚊帐小吊扇夜灯学生大风力家用户外露营
    https://haohuo.jinritemai.com/ecommerce/trade/detail/index.html?id=3749690488916148556&origin_type=2631
  ¥12.50 · Xianyu · seller_g · 跨境户外露营灯太阳能充电野营灯LED球泡灯家用应急夜市地摊灯 太阳能充…
    https://www.goofish.com/item?id=1078495098977
  ...and 15 more in the CSV
```

What it shows: on the first page sorted by sales, the median camping lantern on Taobao costs 6.7 times the median
1688 offer (¥26.30 against ¥3.93). 16 of the 20 1688 suppliers are in Zhejiang, 9 of them in Yiwu. Within the hour
no price moved on Taobao, 1688 or Douyin Shop; what changed was the mix. All ten Xianyu listings and ten of the thirty
Douyin Shop products were new, which moved the Douyin Shop median from ¥15.40 to ¥19.33. An hour is too short to
catch price changes, so run it once a day. A `保温杯` (insulated cup) search the same afternoon put the Taobao/1688 gap at 11.1 times (¥112.62
against ¥10.14): all ten Taobao results were Tmall stores, and all twenty 1688 offers ship from Jinhua or Yongkang in
Zhejiang.

Every run appends to `data/snapshots.csv`, one row per product:

```csv
run_at,source,platform,product_id,title,price,price_high,sku_low,original_price,price_tiers,sold,shop,location,min_order,wants,commission_rate,url
2026-11-22T07:41:59Z,keyword:露营灯,taobao,1027351823739,led应急灯泡夜市摆摊灯户外露营照明USB充电超长续航专用超亮电灯,10.5,,,11.8,,1000,好货严选工厂,浙江 杭州,,,,https://item.taobao.com/item.htm?id=1027351823739
2026-11-22T07:41:59Z,keyword:露营灯,alibaba_1688,800583786261,跨境30LED伸缩露营灯马灯手提营地帐篷灯COB夜钓户外照明野营灯,6.5,,,,,100000,义乌市左玲户外用品有限公司,浙江 金华市,1,,,https://detail.1688.com/offer/800583786261.html
2026-11-22T07:41:59Z,keyword:露营灯,douyin_shop,3848731522114912315,【德系精工】太阳能户外露营照明灯家用夜市摆摊地摊应急灯营地帐篷,16.9,,,,,18333,云境物集,,,,0.16,https://haohuo.jinritemai.com/ecommerce/trade/detail/index.html?id=3848731522114912315&origin_type=2631
2026-11-22T07:41:59Z,track,alibaba_1688,594208233163,不锈钢保温杯316智能水杯男女士茶水分离高颜值礼品定制杯子批发,8.11,12.77,7.3,12.77,,579665,浙江天诺工贸有限公司,浙江省金华市,1,,,https://detail.1688.com/offer/594208233163.html
```

Both runs (144 rows) and the report in English and Chinese are in [`examples/`](examples/); print the report again
with `python3 monitor.py --report-only --out examples`.
<!-- example:end -->

## Quick start

1. Get an API key at [okdata.online](https://okdata.online/signup/?src=gh-taobao-1688-price-monitor) ($0.10 of free credit). After that you
   pay per call; there is no subscription.
2. Put it in your environment and run:

```bash
git clone https://github.com/okdataapi/taobao-1688-price-monitor
cd taobao-1688-price-monitor
export OKDATA_API_KEY=okd_...     # keep it out of code and commits

# see the plan and the most it can cost first (no key needed)
python3 monitor.py --keyword 露营灯 --dry-run

# Python 3.9+. Taobao and 1688 by default: 2 calls, $0.065
python3 monitor.py --keyword 露营灯

# all four platforms, plus two products followed by ID
python3 monitor.py --keyword 露营灯 --platforms all --track taobao:827389194551 --track 1688:594208233163
```

The first run saves a baseline and shows the price spread. Run the same command again tomorrow and the report adds
the price drops and the new products. Add `--lang zh` for the report in Chinese, or print the last report again in
the other language with `--report-only --lang zh` (no calls).

Search in Chinese: the shops write their titles in Chinese, so `露营灯` finds what `camping lantern` does not.

**Following a product.** `--track` takes the link you copy from the browser or `PLATFORM:ID`:

| Platform | Link | As `PLATFORM:ID` |
|---|---|---|
| Taobao & Tmall | `item.taobao.com/item.htm?id=…` or `detail.tmall.com/item.htm?id=…` | `taobao:827389194551` |
| 1688 | `detail.1688.com/offer/<id>.html` | `1688:594208233163` |
| Xianyu | `www.goofish.com/item?id=…` | `xianyu:929052713117` |
| Douyin Shop | `haohuo.jinritemai.com/…?id=…` | `douyin_shop:3800712905230516353` |

## Flags

| Flag | Default | What it does |
|---|---|---|
| `--keyword TEXT` | | Search keywords, as you would type them into the platform's search box. Repeat for more. |
| `--platforms LIST` | `taobao,1688` | Where to search: `taobao`, `1688`, `xianyu`, `douyin_shop` (or `douyin`), comma-separated, or `all`. |
| `--track PLATFORM:ID` | | A product to read every run, as `PLATFORM:ID` or its link. Repeat for more. |
| `--sort sales\|default` | `sales` | Order of Taobao and 1688 results. Xianyu uses its own order; Douyin Shop search has no sort option. |
| `--pages N` | `1` | Search pages per keyword and platform: about 10 products on Taobao and Xianyu, 20 on 1688, 30 on Douyin Shop. |
| `--out DIR` | `data` | Folder for `snapshots.csv`. The file is only ever appended to. |
| `--top N` | `5` | How many price drops and new products the report lists. |
| `--lang en\|zh` | `en` | Language of the report. |
| `--budget USD` | `0.5` | Refuse to start if the run could cost more than this. |
| `--dry-run` | | Print the plan and the most it can cost, then stop. Needs no key. |
| `--report-only` | | Print the report for the CSV in `--out` again. No calls, no key. |

The report goes to stdout; progress and the amount spent go to stderr. Rows are saved after each search and each
tracked product, so a failure halfway keeps what was already fetched.

| Exit code | Meaning |
|---|---|
| `0` | Done |
| `1` | Stopped by an error that would hit every call (bad key, low balance), or every call failed |
| `2` | No key, or a bad flag |
| `3` | The plan could cost more than `--budget`; nothing was called |
| `4` | Done, but some searches or tracked products failed (for example a wrong product ID); the rest was saved |

## What each platform gives

The four platforms do not describe a product the same way, and the search page and the product page of one platform
do not agree either. This is what came back on 2026-11-22:

| | Taobao & Tmall | 1688 | Xianyu | Douyin Shop |
|---|---|---|---|---|
| Search: `price` | Price after the shop's current promotion | Lowest wholesale price | Asking price | Final price |
| Search: `sold` | Buyers in the last month, rounded down (`1000` stands for "1000+") | Units sold, rounded; never above 100,000 in our runs | Not given | Units sold in the last month |
| Search: also | `original_price`, ships from | `min_order`, supplier location | `original_price`, seller's area | `commission_rate` a creator earns per sale |
| Detail: `price` | Lowest variant price, can be above the search price | Headline price; `price_high` is the top of the range | Asking price | **Not given** |
| Detail: `sold` | Not given | Units sold this year | As the listing shows it | Total units sold |
| Detail: also | Every variant's price (`sku_low`, `price_high`) | Variants, `min_order`, tiered prices in `price_tiers` | `wants` (people who tapped "I want") | |

What that means in practice:

- **Compare search with search and detail with detail.** On the same day the same Supor thermos on Tmall was ¥89.90
  in the search results, where Taobao shows the shop's promotion price, and ¥99.90 in its detail answer, which gives
  the variant prices. A 1688 offer showed ¥7.79 in search, ¥8.11 to ¥12.77 in its detail answer, and its cheapest
  variant was ¥7.30. The monitor keeps the two apart: price changes are always measured within the same search or
  the same tracked read.
- **Douyin Shop's detail answer has no price.** To follow the price of a Douyin Shop product, use a keyword that
  finds it; tracking it still records its total sales.
- **1688 tiered prices** (阶梯价, cheaper per unit as the order grows) go into `price_tiers` as returned. Both
  offers we read on 2026-11-22 had none, so `price` to `price_high` is the range to use. `min_order` is the minimum
  order quantity.
- **Sales figures are not comparable across platforms**: last month on Taobao and Douyin Shop, this year on 1688
  detail, and rounded on the Taobao and 1688 search pages (a 1688 offer the search showed as 100,000 had sold
  579,665 this year according to its detail answer).
- **Xianyu is second-hand.** The listings are private sellers' asking prices, often with the new price in
  `original_price`. The CSV takes `wants` from the detail answer only.

## The CSV

Every run appends one row per product to `data/snapshots.csv`:

| Column | |
|---|---|
| `run_at` | When the run started, UTC. Every row of one run has the same value. |
| `source` | `keyword:<text>` for search results, `track` for products read by ID |
| `platform` | `taobao`, `alibaba_1688`, `xianyu` or `douyin_shop` |
| `product_id`, `url` | The product |
| `title` | On one line, cut to 100 characters |
| `price` | In yuan, as described above |
| `price_high` | Top of the price range or the dearest variant (detail answers) |
| `sku_low` | The cheapest variant (detail answers) |
| `original_price` | List price before discount, where shown |
| `price_tiers` | 1688 tiered wholesale prices as JSON, where the offer has them |
| `sold` | As described above; not comparable across platforms |
| `shop` | Shop, supplier or (Xianyu) seller |
| `location` | Ships from (Taobao, 1688) or the seller's area (Xianyu) |
| `min_order` | 1688 minimum order quantity |
| `wants` | Xianyu "I want" count (detail answers) |
| `commission_rate` | Douyin Shop affiliate commission, `0.15` = 15% |

Text that starts like a spreadsheet formula (`=`, `+`, `-`, `@`) gets a leading `'` so Excel shows it instead of
running it.

## How the report works

- **Price spread**: the lowest, median and highest price of each platform's search results in this run. A search
  also returns accessories and neighbours (a `露营灯` search on Taobao returned a ¥6.90 headlamp), so the median says
  more than the minimum. The Taobao ÷ 1688 line divides the two medians.
- **Price drops**: each product's price now against its price the last time it was seen (normally the run before),
  ranked by the relative drop. A product that is both tracked and found by a search counts once, with its detail
  price.
- **New**: search results whose ID was not in any earlier run for the same keyword and platform. Search pages move a
  little between runs, so on a busy keyword read "new" as "new in the top results".
- Leave at least an hour between runs. When the API answers from a copy it fetched a little earlier, the log line
  for that search ends with `(prices as of <time>)`.

## Endpoints and prices

| What | Endpoint | Price |
|---|---|---|
| Taobao & Tmall search, about 10 products a page | [`taobao.products.search`](https://okdata.online/apis/taobao/products/search/?src=gh-taobao-1688-price-monitor) | $0.043 |
| Taobao & Tmall product details | [`taobao.products.get`](https://okdata.online/apis/taobao/products/get/?src=gh-taobao-1688-price-monitor) | $0.033 |
| 1688 search, about 20 products a page | [`alibaba_1688.products.search`](https://okdata.online/apis/alibaba_1688/products/search/?src=gh-taobao-1688-price-monitor) | $0.022 |
| 1688 product details | [`alibaba_1688.products.get`](https://okdata.online/apis/alibaba_1688/products/get/?src=gh-taobao-1688-price-monitor) | $0.022 |
| Xianyu search, about 10 listings a page | [`xianyu.products.search`](https://okdata.online/apis/xianyu/products/search/?src=gh-taobao-1688-price-monitor) | $0.022 |
| Xianyu listing details | [`xianyu.products.get`](https://okdata.online/apis/xianyu/products/get/?src=gh-taobao-1688-price-monitor) | $0.022 |
| Douyin Shop search, about 30 products a page | [`douyin_shop.products.search`](https://okdata.online/apis/douyin_shop/products/search/?src=gh-taobao-1688-price-monitor) | $0.054 |
| Douyin Shop product details | [`douyin_shop.products.get`](https://okdata.online/apis/douyin_shop/products/get/?src=gh-taobao-1688-price-monitor) | $0.039 |

One keyword on Taobao and 1688, once a day: 2 calls, $0.065 a day, about $2 a month. One keyword on all four
platforms: 4 calls, $0.141. Before calling anything, the script reads the current prices from the public catalog
(`GET https://api.okdata.online/v1/catalog`, no key needed), prints the most the run can cost and refuses runs over
`--budget`.

The same key also reads reviews, shop listings and variant stock on these platforms, and 26 other platforms: see the
[Taobao](https://okdata.online/apis/taobao/?src=gh-taobao-1688-price-monitor), [1688](https://okdata.online/apis/alibaba_1688/?src=gh-taobao-1688-price-monitor),
[Xianyu](https://okdata.online/apis/xianyu/?src=gh-taobao-1688-price-monitor) and [Douyin Shop](https://okdata.online/apis/douyin_shop/?src=gh-taobao-1688-price-monitor) endpoints.
Related guides:
[searching 1688 suppliers from outside China](https://okdata.online/answers/1688-supplier-search-outside-china/?src=gh-taobao-1688-price-monitor),
[exporting Xianyu search results](https://okdata.online/answers/xianyu-search-export/?src=gh-taobao-1688-price-monitor),
[Douyin Shop product and review data](https://okdata.online/answers/douyin-shop-products-reviews/?src=gh-taobao-1688-price-monitor) and
[exporting Taobao and Tmall reviews](https://okdata.online/answers/taobao-tmall-reviews-export/?src=gh-taobao-1688-price-monitor).

## Scheduling

### cron

Keep the key in a file only you can read, for example `~/.okdata.env` containing `export OKDATA_API_KEY=okd_...`
(`chmod 600 ~/.okdata.env`), then `crontab -e`:

```cron
# every day at 08:53
53 8 * * * cd "$HOME/taobao-1688-price-monitor" && . "$HOME/.okdata.env" && python3 monitor.py --keyword 露营灯 --track 1688:594208233163 >> "$HOME/price-monitor.log" 2>&1
```

Give the full path to `python3` if cron cannot find it.

### GitHub Actions

[`.github/workflows/monitor.yml`](.github/workflows/monitor.yml) takes a snapshot every day at 00:53 UTC (08:53 in
China) and commits `data/snapshots.csv` back to the repository, so the price history builds up in git.

1. Fork this repository (or use it as a template).
2. Add your key under **Settings → Secrets and variables → Actions → New repository secret**, named `OKDATA_API_KEY`.
3. Under the **Variables** tab, set `KEYWORDS` and `TRACK`, one entry per line, and optionally `PLATFORMS`
   (default `taobao,1688`), `PAGES` and `REPORT_LANG` (`en` or `zh`). Without them it monitors `露营灯` on Taobao
   and 1688.
4. Open the **Actions** tab, enable workflows if GitHub asks (forks start with them off), then
   **monitor → Run workflow** to take the first snapshot now.

The report shows up on each run's summary page. Without the `OKDATA_API_KEY` secret the workflow skips with a
notice instead of failing. The CSV is committed to your repository, so make the repository private if what you
watch is nobody else's business.

## Use it from an AI client

The script is a plain REST client. The same endpoints are also available to AI assistants through okdata's remote
MCP server, `https://api.okdata.online/mcp`, so you can ask "find 1688 factories for 20oz tumblers, compare their
prices and minimum orders with what Tmall shops charge, and answer in English".

Claude Code:

```bash
claude mcp add --transport http okdata https://api.okdata.online/mcp --header 'Authorization: Bearer ${OKDATA_API_KEY}'
```

Cursor, Dify and other clients: see [okdata.online/mcp](https://okdata.online/mcp/?src=gh-taobao-1688-price-monitor).

## Notes

- A sample project by [okdata](https://okdata.online/?src=gh-taobao-1688-price-monitor), not affiliated with Taobao, Tmall, 1688, Xianyu or Douyin.
  The script only calls the okdata API.
- Public product listings and public counts only. Xianyu sellers are private people: use the listings to study
  prices, not to build profiles of the sellers.
- Tests: `python3 -m unittest discover -s tests`. They run against a local mock server (no network, no cost).
- Issues and ideas are welcome.

---

## 中文说明

给一个商品关键词，比如「露营灯」「保温杯」，脚本会在你选的平台上各搜一页：淘宝天猫、1688、闲鱼、抖音电商。每个商品的价格和销量追加进一张 CSV 表，再打印一份短报告：每个平台的最低价、中位价、最高价，淘宝零售中位价是 1688 批发中位价的几倍，你指定跟踪的商品现在多少钱。每天跑一次，报告里还会列出和上次比降价最多的商品，以及新出现的商品。

适合跨境卖家找货源前拿 1688 出厂价对比淘宝零售价，品牌方看自己的品类在国内卖什么价、谁在压价，采购和研究人员攒价格序列，也适合给 AI 智能体接国内电商的实时价格。

一个 Python 文件，只用标准库，Python 3.9 以上就能跑；也可以先在浏览器里试：[Colab 笔记本](https://colab.research.google.com/github/okdataapi/taobao-1688-price-monitor/blob/main/price_monitor.ipynb)。**不用登录淘宝、1688 或抖音，不用 Cookie，不开浏览器**。数据来自 [okdata](https://okdata.online/zh/?src=gh-taobao-1688-price-monitor)，搜索一页：1688 和闲鱼 $0.022，淘宝 $0.043，抖音电商 $0.054。

### 快速开始

1. 在 [okdata](https://okdata.online/zh/signup/?src=gh-taobao-1688-price-monitor) 注册拿一个 Key（以 `okd_` 开头，免费试用（$0.10 额度）），之后按次付费，不用订阅。
2. 运行：

```bash
git clone https://github.com/okdataapi/taobao-1688-price-monitor
cd taobao-1688-price-monitor
export OKDATA_API_KEY=okd_...     # 别写进代码和提交记录

# 先看计划和最多花多少钱（不用 Key，不花钱）
python3 monitor.py --keyword 露营灯 --lang zh --dry-run

# 默认只搜淘宝和 1688：2 次调用，$0.065
python3 monitor.py --keyword 露营灯 --lang zh

# 四个平台都搜，再按 ID 跟踪两个商品
python3 monitor.py --keyword 露营灯 --platforms all --track taobao:827389194551 --track 1688:594208233163 --lang zh
```

第一次运行存下基准快照，报告里先给出价格分布。明天再跑同一条命令，报告里就会多出降价榜和新商品。想把上一份报告换成英文再看一遍，用 `--report-only --lang en`，不调用接口。

<!-- example-zh:start -->
下面是 2026-11-22 隔一小时的两次真实运行里第二次的报告：关键词「露营灯」搜四个平台，再按 ID 跟踪一个天猫保温杯和一个 1688 保温杯，每次 6 次调用，$0.196。略去了 stderr 里的进度信息；闲鱼卖家是个人，昵称换成了 `seller_a` 这样的代号。

```console
$ python3 monitor.py --keyword 露营灯 --platforms all --track taobao:827389194551 --track 1688:594208233163 --lang zh
电商价格监控 2026-11-22T07:41:59Z（上次 2026-11-22T06:39:36Z）

「露营灯」的价格（元）：
  平台          件数      最低      中位      最高
  淘宝            10      6.90     26.30     36.79
  1688            20      1.05      3.93     27.00
  闲鱼            10      9.00     22.00    210.00
  抖音电商        30      4.99     19.33    159.99
  淘宝的中位价是 1688 的 6.7 倍。

跟踪的商品：
  ¥99.90 · 淘宝 · 苏泊尔餐饮具旗舰店 · 之前 ¥99.90 · 苏泊尔保温杯316L不锈钢高颜值男女学生儿童便携泡茶水杯
    https://detail.tmall.com/item.htm?id=827389194551
  ¥8.11 · 1688 · 浙江天诺工贸有限公司 · 之前 ¥8.11，销量 579,665 · 不锈钢保温杯316智能水杯男女士茶水分离高颜值礼品定制杯子批发
    https://detail.1688.com/offer/594208233163.html

和上次比降价最多：
  之前见过的 52 个商品：降价 0 个，涨价 0 个，没变 52 个。
  没有商品降价。

搜索结果里新出现的商品：20 个
  ¥158.00 · 闲鱼 · seller_h · 铁锚牌老汽灯，带原包装箱，成色还可以，有点年代感，收藏、摆件 都很合适…
    https://www.goofish.com/item?id=1013583230890
  ¥38.00 · 抖音电商 · 暗月官方旗舰店 · 暗月强光手电筒变焦超亮激光户外可充电远射便捷多功能耐用长续航
    https://haohuo.jinritemai.com/ecommerce/trade/detail/index.html?id=3665820867289547181&origin_type=2631
  ¥210.00 · 闲鱼 · seller_i · 科乐曼 悬挂式E灯 金属绿 2206770 日本代购 49928261…
    https://www.goofish.com/item?id=1077106890045
  ¥29.90 · 抖音电商 · 超星捷个护工厂店 · 可充电小吊扇学生宿舍床上蚊帐小吊扇夜灯学生大风力家用户外露营
    https://haohuo.jinritemai.com/ecommerce/trade/detail/index.html?id=3749690488916148556&origin_type=2631
  ¥12.50 · 闲鱼 · seller_g · 跨境户外露营灯太阳能充电野营灯LED球泡灯家用应急夜市地摊灯 太阳能充…
    https://www.goofish.com/item?id=1078495098977
  ……另外 15 个在 CSV 里
```

按销量排的第一页里，淘宝露营灯的中位价是 1688 的 6.7 倍（¥26.30 对 ¥3.93）。1688 的 20 家供应商有 16 家在浙江，其中 9 家在义乌。一小时内淘宝、1688 和抖音电商没有一个商品改价，变的是搜出来的商品：闲鱼 10 条全换了，抖音电商 30 个里换了 10 个，抖音的中位价因此从 ¥15.40 变成 ¥19.33。一小时太短，看不出价格变化，建议每天跑一次。同一天下午搜「保温杯」，淘宝和 1688 的差距是 11.1 倍（¥112.62 对 ¥10.14）：淘宝前十全是天猫店，1688 前二十家供应商全在浙江金华和永康。

两次运行的完整 CSV（144 行）和中英文报告在 [`examples/`](examples/) 目录，`python3 monitor.py --report-only --out examples --lang zh` 可以重新打印报告。
<!-- example-zh:end -->

### 参数

| 参数 | 默认 | 作用 |
|---|---|---|
| `--keyword 关键词` | | 搜索关键词，和在平台搜索框里输入的一样。可以写多个。 |
| `--platforms 平台` | `taobao,1688` | 搜哪些平台：`taobao`、`1688`、`xianyu`、`douyin_shop`（也可以写 `douyin`），逗号分隔，或者 `all` |
| `--track 平台:ID` | | 每次都按 ID 读一遍的商品，写 `1688:594208233163` 或者直接贴商品链接。可以写多个。 |
| `--sort sales\|default` | `sales` | 淘宝和 1688 的排序：销量或综合。闲鱼用它自己的综合排序，抖音电商搜索没有排序选项。 |
| `--pages N` | `1` | 每个关键词在每个平台取几页。一页约有淘宝、闲鱼 10 个，1688 20 个，抖音电商 30 个。 |
| `--out 目录` | `data` | `snapshots.csv` 放在哪个目录，只追加不覆盖 |
| `--top N` | `5` | 报告里列几个降价商品和新商品 |
| `--lang en\|zh` | `en` | 报告用英文还是中文 |
| `--budget 美元` | `0.5` | 这次运行最多可能花的钱超过这个数就不跑 |
| `--dry-run` | | 只打印计划和最多花多少钱，不调用，不需要 Key |
| `--report-only` | | 按现有 CSV 再打印一遍报告，不调用，不需要 Key |

商品链接这样认：淘宝天猫是 `item.taobao.com` 或 `detail.tmall.com` 链接里 `id=` 后面的数字，1688 是 `detail.1688.com/offer/数字.html`，闲鱼是 `goofish.com/item?id=数字`，抖音电商是 `haohuo.jinritemai.com` 链接里 `id=` 后面的数字。

### 各平台给什么字段

四个平台描述商品的方式不一样，同一个平台的搜索结果和商品详情也对不上。以 2026-11-22 的实际返回为准：

- **淘宝天猫**：搜索结果的价格是店铺当前活动价，销量是近一个月付款人数，按档取整（`1000` 表示「1000+」）；详情给各规格的价格，`price` 取最低的规格价，可能比搜索结果里的价高，详情不给销量。同一个苏泊尔保温杯，搜索结果里是 ¥89.90，详情里是 ¥99.90。
- **1688**：搜索结果给最低批发价、起批量（`min_order`）、供应商所在地，销量是取整后的数，我们跑的几次里最高显示 100,000。详情给价格区间（`price` 到 `price_high`）、各规格价、今年销量和阶梯批发价（`price_tiers`）。我们读到的两个商品都没有阶梯价；其中一个搜索结果显示 ¥7.79，详情区间 ¥8.11 到 ¥12.77，最便宜的规格 ¥7.30，搜索结果显示销量 100,000，详情里今年实际卖了 579,665 件。
- **闲鱼**：二手个人卖家的标价，常带原价（`original_price`）和卖家所在地区。「想要」人数（`wants`）只从详情里取。
- **抖音电商**：搜索结果给到手价、近一个月销量和达人带货佣金比例（`commission_rate`，`0.15` 就是 15%）。**详情接口不返回价格**，只有累计销量；想跟踪抖音商品的价格，就用能搜到它的关键词。

所以报告比较价格时，只拿同一个关键词的搜索结果比，或者拿同一个跟踪商品的详情比，不会把搜索价和详情价混在一起。一个商品既被跟踪又出现在搜索结果里时，降价榜只算一次，用详情价。各平台的销量口径不同，不能横着比。

### 报告怎么算

- **价格分布**：本次每个平台搜索结果的最低价、中位价、最高价。搜索结果里会混进配件和相近商品（比如淘宝搜「露营灯」会搜出一个 ¥6.90 的头灯），所以中位价比最低价更有参考意义。「淘宝中位价是 1688 的几倍」就是两个中位价相除。
- **降价榜**：每个商品这次的价格和它上一次出现时的价格比（一般就是上一次运行），按降价百分比排序。
- **新出现的商品**：这次搜到、以前同一关键词同一平台从没搜到过的商品。搜索结果本身每次会有些轮换，热门关键词下的「新」更接近「新挤进前排」。
- 两次运行至少隔一小时。接口用了稍早抓到的数据时，日志那一行末尾会注明 `(prices as of 时间)`。

### 花多少钱

一个关键词只搜淘宝和 1688，每天一次：2 次调用，每天 $0.065，一个月约 $2。四个平台都搜是 4 次调用 $0.141。跟踪商品每个每次：淘宝 $0.033，1688 和闲鱼 $0.022，抖音电商 $0.039。脚本调用前会先读公开价格表（不用 Key），打印这次最多花多少钱，超过 `--budget` 就不跑。

同一个 Key 还能取这些平台的商品评价、店铺商品列表和规格库存，以及其他 26 个平台的数据，见 [淘宝天猫](https://okdata.online/zh/apis/taobao/?src=gh-taobao-1688-price-monitor)、[1688](https://okdata.online/zh/apis/alibaba_1688/?src=gh-taobao-1688-price-monitor)、[闲鱼](https://okdata.online/zh/apis/xianyu/?src=gh-taobao-1688-price-monitor)、[抖音电商](https://okdata.online/zh/apis/douyin_shop/?src=gh-taobao-1688-price-monitor) 接口列表。相关问答：[人在海外怎么让 AI 或脚本去 1688 找货源、查工厂价](https://okdata.online/zh/answers/1688-supplier-search-outside-china/?src=gh-taobao-1688-price-monitor)、[闲鱼商品怎么按关键词搜索并导出](https://okdata.online/zh/answers/xianyu-search-export/?src=gh-taobao-1688-price-monitor)、[抖音电商的商品和评价数据怎么拿](https://okdata.online/zh/answers/douyin-shop-products-reviews/?src=gh-taobao-1688-price-monitor)、[淘宝天猫商品评价怎么批量导出](https://okdata.online/zh/answers/taobao-tmall-reviews-export/?src=gh-taobao-1688-price-monitor)。

### 每天自动跑

- **cron**：把 `export OKDATA_API_KEY=okd_...` 写进只有你能读的 `~/.okdata.env`，再在 `crontab -e` 里加一行，写法见上面英文部分。
- **GitHub Actions**：Fork 本仓库，在 Settings → Secrets and variables → Actions 里加 Secret `OKDATA_API_KEY`，在 Variables 里设置 `KEYWORDS` 和 `TRACK`（每行一个），可选 `PLATFORMS`（默认 `taobao,1688`）、`PAGES`，想看中文报告就把 `REPORT_LANG` 设成 `zh`，然后在 Actions 页面手动运行一次 monitor。之后每天北京时间 08:53 自动拍一份快照，把 CSV 提交回仓库。没加 Secret 时这个任务会提示一句然后跳过，不会报错。CSV 会提交到你的仓库里，盯的是竞品的话建议把仓库设成私有。

### 让 AI 直接用

同样的接口也可以通过 okdata 的远程 MCP（`https://api.okdata.online/mcp`）接进 Claude Code、Cursor、Dify，直接问「帮我在 1688 找 20oz 保温杯的工厂，把价格和起批量跟天猫店的售价对比一下」。接入方法见 [MCP 接入说明](https://okdata.online/zh/mcp/?src=gh-taobao-1688-price-monitor)。

### 说明

- 这是 [okdata](https://okdata.online/zh/?src=gh-taobao-1688-price-monitor) 的示例项目，和淘宝、天猫、1688、闲鱼、抖音官方无关，脚本只调用 okdata 的接口。
- 只取公开的商品信息和公开数字。闲鱼卖家是个人，请用这些数据研究价格，不要给卖家建档。
- 测试：`python3 -m unittest discover -s tests`，跑在本地模拟服务上，不联网，不花钱。

## License

MIT, see [LICENSE](LICENSE).
