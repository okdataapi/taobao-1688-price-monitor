"""Runs monitor.py against a local mock of the okdata API with canned answers. No network, no real key."""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
os.environ["NO_PROXY"] = "*"

import monitor as tool  # noqa: E402
from mock_okdata import TEST_KEY, MockOkdata, error, ok  # noqa: E402

API = json.loads((FIXTURES / "api.json").read_text(encoding="utf-8"))
TRACKED = ["--track", "https://detail.1688.com/offer/594208233163.html", "--track", "xianyu:929052713117",
           "--track", "douyin:3800712905230516353"]
ARGS = ["--keyword", "  保温　杯 ", "--platforms", "all", *TRACKED]
SEARCHES = {"taobao": "taobao.products.search", "alibaba_1688": "alibaba_1688.products.search",
            "xianyu": "xianyu.products.search", "douyin_shop": "douyin_shop.products.search"}


class MonitorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.run_index = 0
        routes = {f"/v1/{p}/products/search": self.search_page(p) for p in SEARCHES}
        routes.update({f"/v1/{p}/products/get": self.detail for p in SEARCHES})
        self.api = MockOkdata(routes)
        tool.API = self.api.url
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "data"

    def tearDown(self) -> None:
        self.api.close()
        self.tmp.cleanup()

    def search_page(self, platform: str):
        def answer(query: dict) -> tuple:
            pages = API["runs"][self.run_index]["search"][platform]
            page = int(query.get("cursor") or "0")
            more = str(page + 1) if page + 1 < len(pages) else None
            return 200, ok(SEARCHES[platform], items=pages[page], next_cursor=more, amount="0.02")
        return answer

    def detail(self, query: dict) -> tuple:
        item = API["runs"][self.run_index]["get"].get(query["id"])
        if item is None:
            return 404, error("not_found")
        return 200, ok("x.products.get", item=item, amount="0.02")

    def run_tool(self, *argv: str, key: str = TEST_KEY, run: int = 0, at: str = "") -> tuple:
        self.run_index = run
        os.environ["OKDATA_API_KEY"] = key
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = tool.main([*argv, "--out", str(self.out)], now=lambda: at or API["runs"][run]["run_at"])
        return code, out.getvalue(), err.getvalue()

    def snapshots(self) -> str:
        return (self.out / "snapshots.csv").read_text(encoding="utf-8")

    def rows(self) -> list:
        return list(csv.DictReader(io.StringIO(self.snapshots())))

    def test_two_runs_append_one_csv_and_report_drops_and_new_products(self) -> None:
        code, out, log = self.run_tool(*ARGS, "--pages", "2", run=0)
        self.assertEqual(code, 0, log)
        self.assertIn("(first run)", out)
        self.assertIn("spent $0.16", log)  # 5 search pages + 3 tracked products
        code, out, log = self.run_tool(*ARGS, "--pages", "2", run=1)
        self.assertEqual(code, 0, log)
        self.assertEqual(self.snapshots(), (FIXTURES / "expected-snapshots.csv").read_text(encoding="utf-8"))
        self.assertEqual(out, (FIXTURES / "expected-report.txt").read_text(encoding="utf-8"))

    def test_search_parameters(self) -> None:
        self.run_tool(*ARGS, "--pages", "2", run=0)
        calls = [(r["path"], r["query"]) for r in self.api.paid()]
        searches = [(path.split("/")[2], q) for path, q in calls if path.endswith("/search")]
        self.assertEqual({q["query"] for _, q in searches}, {"保温 杯"})
        self.assertEqual({q["view"] for _, q in calls}, {"full"})
        self.assertEqual({p: q.get("sort") for p, q in searches},
                         {"taobao": "sales", "alibaba_1688": "sales", "xianyu": None, "douyin_shop": None})
        self.assertEqual([q.get("cursor") for p, q in searches if p == "alibaba_1688"], [None, "1"])
        details = sorted(q["id"] for path, q in calls if path.endswith("/get"))
        self.assertEqual(details, ["3800712905230516353", "594208233163", "929052713117"])

    def test_report_in_chinese(self) -> None:
        self.run_tool(*ARGS, "--pages", "2", run=0)
        code, out, log = self.run_tool(*ARGS, "--pages", "2", "--lang", "zh", run=1)
        self.assertEqual(code, 0, log)
        self.assertEqual(out, (FIXTURES / "expected-report-zh.txt").read_text(encoding="utf-8"))
        self.assertIn("https://okdata.online/zh/", tool.links("zh")[0])

    def test_report_only_reprints_without_calling(self) -> None:
        self.run_tool(*ARGS, "--pages", "2", run=0)
        self.run_tool(*ARGS, "--pages", "2", run=1)
        before = len(self.api.requests)
        code, out, _ = self.run_tool("--report-only", key="")
        self.assertEqual(code, 0)
        self.assertEqual(out, (FIXTURES / "expected-report.txt").read_text(encoding="utf-8"))
        self.assertEqual(len(self.api.requests), before)

    def test_platform_fields_land_in_their_columns(self) -> None:
        self.run_tool(*ARGS, run=0)
        rows = {(r["source"], r["platform"], r["product_id"]): r for r in self.rows()}
        offer = rows[("track", "alibaba_1688", "594208233163")]
        self.assertEqual((offer["price"], offer["price_high"], offer["sku_low"], offer["min_order"], offer["sold"]),
                         ("8.11", "12.77", "7.3", "1", "579665"))
        douyin = rows[("track", "douyin_shop", "3800712905230516353")]
        self.assertEqual((douyin["price"], douyin["sold"]), ("", "473810"))  # the detail answer has no price
        listing = rows[("keyword:保温 杯", "xianyu", "929052713117")]
        self.assertEqual((listing["price"], listing["original_price"], listing["wants"], listing["location"]),
                         ("55", "138", "", "上海"))
        self.assertEqual(rows[("track", "xianyu", "929052713117")]["wants"], "317")
        shop = rows[("keyword:保温 杯", "douyin_shop", "3826520231778582978")]
        self.assertEqual(shop["commission_rate"], "0.15")

    def test_csv_rows_are_clipped_and_safe_for_spreadsheets(self) -> None:
        self.run_tool(*ARGS, run=0)
        rows = self.rows()
        formula = next(r for r in rows if "HYPERLINK" in r["title"])
        self.assertTrue(formula["title"].startswith("'="))
        self.assertNotIn("\n", formula["title"])
        self.assertTrue(formula["shop"].startswith("'@"))
        long_title = next(r for r in rows if r["product_id"] == "827389194551")
        self.assertEqual(len(long_title["title"]), tool.TITLE_LIMIT)
        self.assertTrue(long_title["title"].endswith("…"))

    def test_dry_run_needs_no_key_and_calls_nothing_paid(self) -> None:
        code, _, log = self.run_tool(*ARGS, "--dry-run", key="")
        self.assertEqual(code, 0, log)
        self.assertEqual(self.api.paid(), [])
        self.assertIn("at most $0.224", log)  # 0.043 + 0.022 + 0.022 + 0.054, then 0.022 + 0.022 + 0.039
        self.assertFalse((self.out / "snapshots.csv").exists())

    def test_default_platforms_are_taobao_and_1688(self) -> None:
        code, _, log = self.run_tool("--keyword", "保温杯", "--dry-run", key="")
        self.assertEqual(code, 0)
        self.assertIn("at most $0.065", log)
        self.assertNotIn("xianyu", log)

    def test_live_catalog_prices_win(self) -> None:
        self.api.prices = {"taobao.products.search": "0.05"}
        code, _, log = self.run_tool("--keyword", "保温杯", "--dry-run", key="")
        self.assertEqual(code, 0)
        self.assertIn("at most $0.072", log)  # 0.05 live + 0.022 built in

    def test_over_budget_calls_nothing(self) -> None:
        code, _, log = self.run_tool(*ARGS, "--pages", "5", run=0)
        self.assertEqual(code, 3)
        self.assertIn("over the --budget of $0.5", log)
        self.assertEqual(self.api.paid(), [])

    def test_bad_key_stops_the_run(self) -> None:
        code, out, log = self.run_tool(*ARGS, key="okd_wrong", run=0)
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("unauthorized", log)
        self.assertEqual(len(self.api.paid()), 1)  # stopped after the first call

    def test_missing_key(self) -> None:
        code, _, log = self.run_tool(*ARGS, key="", run=0)
        self.assertEqual(code, 2)
        self.assertIn("OKDATA_API_KEY is not set", log)

    def test_a_failed_track_keeps_the_other_rows(self) -> None:
        code, out, log = self.run_tool("--keyword", "保温杯", "--track", "taobao:1234567890", run=0)
        self.assertEqual(code, 4)
        self.assertIn("not_found", log)
        self.assertIn("Check the product ID", log)
        self.assertRegex(out, r"Taobao +3 ")

    def test_foreign_csv_is_refused_before_any_paid_call(self) -> None:
        self.out.mkdir(parents=True)
        (self.out / "snapshots.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        code, _, log = self.run_tool(*ARGS, run=0)
        self.assertEqual(code, 1)
        self.assertIn("other columns", log)
        self.assertEqual(self.api.paid(), [])

    def test_a_run_that_missed_a_platform_does_not_stop_the_comparison(self) -> None:
        self.run_tool("--keyword", "保温杯", run=0)  # Taobao and 1688
        self.run_tool("--keyword", "保温杯", "--platforms", "taobao", run=1)  # a one-off run without 1688
        code, out, log = self.run_tool("--keyword", "保温杯", "--platforms", "1688", run=1, at="2026-11-22T00:53:00Z")
        self.assertEqual(code, 0, log)
        self.assertIn("Of 2 products seen before: 1 cheaper, 1 dearer, 0 unchanged.", out)
        self.assertIn("¥7.79 → ¥7.50", out)  # compared with the first run, the last one that had 1688

    def test_odd_answers_do_not_crash_the_run(self) -> None:
        self.api.routes["/v1/taobao/products/search"] = lambda q: (200, {**ok("taobao.products.search", items=[]),
                                                                        "data": [], "page": "?", "meta": None})
        self.api.routes["/v1/alibaba_1688/products/get"] = lambda q: (
            200, ok("alibaba_1688.products.get", item={"title": "无 ID", "price": 0, "ext": {"skus": 7}}))
        code, out, log = self.run_tool("--keyword", "保温杯", "--track", "1688:594208233163", run=0)
        self.assertEqual(code, 0, log)
        row = next(r for r in self.rows() if r["source"] == "track")
        self.assertEqual((row["product_id"], row["price"], row["sku_low"]), ("594208233163", "0", ""))
        self.assertIn("no price in this answer · 1688", out)  # a price of 0 is not a price

    def test_nothing_to_compare_is_said_plainly(self) -> None:
        self.run_tool("--keyword", "保温杯", run=0)
        code, out, _ = self.run_tool("--keyword", "露营灯", run=1)
        self.assertEqual(code, 0)
        self.assertIn("No product has a price in this run and an earlier one yet.", out)

    def test_retry_reuses_the_idempotency_key(self) -> None:
        answers = [(503, error("service_unavailable", retry="yes")),
                   (200, ok("taobao.products.search", items=[], amount="0.043"))]
        self.api.routes["/v1/taobao/products/search"] = lambda q: answers.pop(0)
        client = tool.Okdata(TEST_KEY, sleep=lambda s: None)
        client.call("taobao.products.search", query="保温杯")
        keys = [r["headers"]["idempotency-key"] for r in self.api.paid()]
        self.assertEqual(len(keys), 2)
        self.assertEqual(keys[0], keys[1])
        self.assertEqual(client.spent, Decimal("0.043"))


class RowTest(unittest.TestCase):
    def test_tiered_prices_are_kept_as_json(self) -> None:
        item = {"id": "1", "title": "x", "price": 5, "ext": {"tiered_prices": [{"min": 2, "price": 5}], "skus": []}}
        row = tool.to_row("t", "track", "alibaba_1688", item)
        self.assertEqual(row["price_tiers"], '[{"min":2,"price":5}]')
        self.assertIsNone(row["sku_low"])

    def test_odd_values_do_not_become_prices(self) -> None:
        item = {"id": "1", "price": "12.5-15", "original_price": True, "sold": -3, "ext": None, "shop": "x"}
        row = tool.to_row("t", "keyword:k", "taobao", item)
        self.assertEqual((row["price"], row["original_price"], row["sold"], row["shop"]), (None, None, None, ""))

    def test_median(self) -> None:
        self.assertEqual(tool.median([Decimal(3), Decimal(1), Decimal(2)]), Decimal(2))
        self.assertEqual(tool.median([Decimal("1"), Decimal("2.5")]), Decimal("1.75"))


class ArgumentTest(unittest.TestCase):
    def test_track_accepts_links_and_platform_ids(self) -> None:
        cases = {
            "https://item.taobao.com/item.htm?spm=a1z10&id=708174321498": ("taobao", "708174321498"),
            "https://detail.tmall.com/item.htm?id=827389194551&skuId=1": ("taobao", "827389194551"),
            "https://detail.1688.com/offer/594208233163.html?spm=x": ("alibaba_1688", "594208233163"),
            "https://www.goofish.com/item?spm=a&id=929052713117": ("xianyu", "929052713117"),
            "https://haohuo.jinritemai.com/ecommerce/trade/detail/index.html?id=3800712905230516353&origin_type=1":
                ("douyin_shop", "3800712905230516353"),
            " 1688:594208233163 ": ("alibaba_1688", "594208233163"),
            "tmall:827389194551": ("taobao", "827389194551"),
            "douyin_shop:3800712905230516353": ("douyin_shop", "3800712905230516353"),
        }
        for value, expected in cases.items():
            self.assertEqual(tool.track(value), expected, value)
        for bad in ("", "594208233163", "jd:123456789", "taobao:abc", "https://item.jd.com/100012043978.html",
                    "https://nottaobao.com/item.htm?id=708174321498"):
            with self.assertRaises(Exception):
                tool.track(bad)

    def test_platform_lists(self) -> None:
        self.assertEqual(tool.platform_list("all"), list(tool.PLATFORMS))
        self.assertEqual(tool.platform_list("1688, Taobao,1688"), ["alibaba_1688", "taobao"])
        self.assertEqual(tool.platform_list("douyin,goofish"), ["douyin_shop", "xianyu"])
        for bad in ("", ",", "jd", "taobao,amazon"):
            with self.assertRaises(Exception):
                tool.platform_list(bad)

    def test_keywords(self) -> None:
        self.assertEqual(tool.keyword(" 露营　 灯 "), "露营 灯")
        for bad in ("", "   ", "长" * 51):
            with self.assertRaises(Exception):
                tool.keyword(bad)

    def test_needs_something_to_monitor(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            tool.parse_args([])

    def test_duplicates_are_called_once(self) -> None:
        calls = tool.plan_calls(["灯", "灯"], ["taobao"], [("taobao", "1"), ("taobao", "1")], "sales")
        self.assertEqual([(c[0], c[2]) for c in calls], [("keyword:灯", "taobao.products.search"),
                                                         ("track", "taobao.products.get")])


if __name__ == "__main__":
    unittest.main()
