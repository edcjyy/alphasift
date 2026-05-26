import pandas as pd
import pytest

from alphasift.snapshot import (
    _normalize,
    _prepare_tushare_snapshot,
    fetch_cn_snapshot,
    fetch_snapshot_with_fallback,
)


def test_normalize_efinance_maps_pb_ratio():
    df = pd.DataFrame(
        [
            {
                "股票代码": "000001",
                "股票名称": "平安银行",
                "最新价": "10.00",
                "涨跌幅": "1.23",
                "成交额": "123456789",
                "总市值": "1000000000",
                "流通市值": "800000000",
                "动态市盈率": "5.2",
                "市净率": "0.8",
                "量比": "1.1",
                "换手率": "2.5",
                "所属行业": "银行",
                "概念题材": "中特估,低估值",
            }
        ]
    )

    normalized = _normalize(df, source="efinance")

    assert normalized.loc[0, "pb_ratio"] == 0.8
    assert normalized.loc[0, "pe_ratio"] == 5.2
    assert normalized.loc[0, "industry"] == "银行"
    assert normalized.loc[0, "concepts"] == "中特估,低估值"


def test_prepare_tushare_snapshot_maps_fields_and_units():
    daily = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20260430",
                "close": "10.00",
                "pct_chg": "1.23",
                "amount": "123456.789",
            }
        ]
    )
    daily_basic = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "turnover_rate": "2.5",
                "volume_ratio": "1.1",
                "pe": "5.2",
                "pb": "0.8",
                "total_mv": "100000",
                "circ_mv": "80000",
            }
        ]
    )
    stock_basic = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "symbol": "000001",
                "name": "平安银行",
                "industry": "银行",
            }
        ]
    )

    normalized = _prepare_tushare_snapshot(daily, daily_basic, stock_basic)

    assert normalized.loc[0, "code"] == "000001"
    assert normalized.loc[0, "name"] == "平安银行"
    assert normalized.loc[0, "price"] == 10.0
    assert normalized.loc[0, "change_pct"] == 1.23
    assert normalized.loc[0, "amount"] == pytest.approx(123456789)
    assert normalized.loc[0, "total_mv"] == pytest.approx(1000000000)
    assert normalized.loc[0, "circ_mv"] == pytest.approx(800000000)
    assert normalized.loc[0, "pe_ratio"] == 5.2
    assert normalized.loc[0, "pb_ratio"] == 0.8
    assert normalized.loc[0, "volume_ratio"] == 1.1
    assert normalized.loc[0, "turnover_rate"] == 2.5
    assert normalized.loc[0, "industry"] == "银行"
    assert normalized.attrs["snapshot_source"] == "tushare"


def test_fetch_tushare_requires_token(monkeypatch):
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    monkeypatch.delenv("TUSHARE_API_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="TUSHARE_TOKEN"):
        fetch_cn_snapshot("tushare")


def test_fetch_tushare_uses_proxy_when_configured(monkeypatch):
    """When TUSHARE_API_URL is set, the pro api object should have its
    internal URL overridden to the proxy address."""
    monkeypatch.setenv("TUSHARE_TOKEN", "relay-token-123")
    monkeypatch.setenv("TUSHARE_API_URL", "http://my-proxy/tushare")

    captured = {}

    class FakePro:
        def __init__(self, token):
            self._token = token
            self._url = "https://api.tushare.pro"

        # Simulate the name-mangled attributes that the proxy code sets
        @property
        def _DataApi__token(self):
            return self._token

        @_DataApi__token.setter
        def _DataApi__token(self, value):
            self._token = value

        @property
        def _DataApi__http_url(self):
            return self._url

        @_DataApi__http_url.setter
        def _DataApi__http_url(self, value):
            self._url = value

        def trade_cal(self, **kwargs):
            return pd.DataFrame([{"cal_date": "20260430", "is_open": "1"}])

        def daily(self, **kwargs):
            captured["daily_called"] = True
            return pd.DataFrame([{
                "ts_code": "000001.SZ",
                "trade_date": "20260430",
                "close": 10.0,
                "pct_chg": 1.23,
                "amount": 123456.789,
            }])

        def daily_basic(self, **kwargs):
            return pd.DataFrame([{
                "ts_code": "000001.SZ",
                "turnover_rate": 2.5,
                "volume_ratio": 1.1,
                "pe": 5.2,
                "pb": 0.8,
                "total_mv": 100000,
                "circ_mv": 80000,
            }])

        def stock_basic(self, **kwargs):
            return pd.DataFrame([{
                "ts_code": "000001.SZ",
                "symbol": "000001",
                "name": "平安银行",
                "industry": "银行",
            }])

    import tushare as ts
    monkeypatch.setattr(ts, "pro_api", lambda token: FakePro(token))

    df = fetch_cn_snapshot("tushare")
    assert captured.get("daily_called")
    assert len(df) == 1


def test_fetch_tushare_no_proxy_uses_official(monkeypatch):
    """When TUSHARE_API_URL is NOT set, the pro api object keeps its
    original official URL (no override)."""
    monkeypatch.setenv("TUSHARE_TOKEN", "official-token")
    monkeypatch.delenv("TUSHARE_API_URL", raising=False)

    captured = {}

    class FakePro:
        def __init__(self, token):
            self._token = token
            self._url = "https://api.tushare.pro"
            self.token_set_count = 0
            self.url_set_count = 0

        @property
        def _DataApi__token(self):
            return self._token

        @_DataApi__token.setter
        def _DataApi__token(self, value):
            self._token = value
            self.token_set_count += 1

        @property
        def _DataApi__http_url(self):
            return self._url

        @_DataApi__http_url.setter
        def _DataApi__http_url(self, value):
            self._url = value
            self.url_set_count += 1

        def trade_cal(self, **kwargs):
            return pd.DataFrame([{"cal_date": "20260430", "is_open": "1"}])

        def daily(self, **kwargs):
            captured["daily_called"] = True
            return pd.DataFrame([{
                "ts_code": "000001.SZ",
                "trade_date": "20260430",
                "close": 10.0,
                "pct_chg": 1.23,
                "amount": 123456.789,
            }])

        def daily_basic(self, **kwargs):
            return pd.DataFrame([{
                "ts_code": "000001.SZ",
                "turnover_rate": 2.5,
                "volume_ratio": 1.1,
                "pe": 5.2,
                "pb": 0.8,
                "total_mv": 100000,
                "circ_mv": 80000,
            }])

        def stock_basic(self, **kwargs):
            return pd.DataFrame([{
                "ts_code": "000001.SZ",
                "symbol": "000001",
                "name": "平安银行",
                "industry": "银行",
            }])

    import tushare as ts
    monkeypatch.setattr(ts, "pro_api", lambda token: FakePro(token))

    df = fetch_cn_snapshot("tushare")
    assert captured.get("daily_called")
    assert len(df) == 1


def test_fetch_snapshot_with_fallback_attaches_source_errors(monkeypatch):
    def fake_fetch(source):
        if source == "bad":
            raise RuntimeError("bad source")
        return pd.DataFrame([{"code": "000001", "name": "示例", "price": 10.0}])

    monkeypatch.setattr("alphasift.snapshot.fetch_cn_snapshot", fake_fetch)

    df = fetch_snapshot_with_fallback(["bad", "good"])

    assert df.attrs["source_errors"] == ["bad: bad source"]


def test_fetch_snapshot_with_fallback_skips_missing_required_columns(monkeypatch):
    def fake_fetch(source):
        if source == "missing_pb":
            return pd.DataFrame([{"code": "000001", "name": "示例", "price": 10.0}])
        return pd.DataFrame([{
            "code": "000001",
            "name": "示例",
            "price": 10.0,
            "pb_ratio": 0.8,
        }])

    monkeypatch.setattr("alphasift.snapshot.fetch_cn_snapshot", fake_fetch)

    df = fetch_snapshot_with_fallback(
        ["missing_pb", "complete"],
        required_columns=["price", "pb_ratio"],
    )

    assert df.attrs["source_errors"] == [
        "missing_pb: missing required columns pb_ratio"
    ]
    assert df.loc[0, "pb_ratio"] == 0.8


def test_fetch_snapshot_with_fallback_raises_all_errors(monkeypatch):
    monkeypatch.setattr(
        "alphasift.snapshot.fetch_cn_snapshot",
        lambda source: (_ for _ in ()).throw(RuntimeError(source)),
    )

    with pytest.raises(RuntimeError, match="a: a; b: b"):
        fetch_snapshot_with_fallback(["a", "b"])
