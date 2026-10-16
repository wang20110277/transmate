"""股票数据工具：Tushare + akshare 混合数据源。

按实测可用性分工——Tushare token 已配置，但部分 pro 接口在当前权限下限 1 次/小时，
调一次就撞限流，因此改用 akshare（免费、无调用频次限制）：

- Tushare：日线 pro.daily、实时行情 realtime_quote
- akshare：个股信息、股票搜索、指数日线、每日基本面
  （对应 tushare 的 stock_basic / index_daily / daily_basic，这仨实测均 1 次/小时）

单位均已与 akshare 同源数据交叉核对过，改动前请先复核，不要凭感觉换算：
- pro.daily：vol=手，amount=千元
- realtime_quote：列名全大写，VOLUME=股，AMOUNT=元（VOLUME×均价 ≡ AMOUNT 已验证）
- 东财指数日线 stock_zh_index_daily_em：volume=手，amount=元
- 百度估值 stock_zh_valuation_baidu：date/value，市值单位为亿元
"""

import logging
import math
import time
import warnings
from datetime import datetime, timedelta

import pandas as pd
import tushare as ts
from langchain_core.tools import tool

from app.core.config import TUSHARE_TOKEN

logger = logging.getLogger(__name__)

# 代码表/行业板块表变化慢，缓存 1 小时（首次拉取约 16s / 6s，缓存后无感）
_CACHE_TTL = 3600.0
_cache: dict[str, tuple[float, object]] = {}

_akshare_mod = None
_pro_client = None
_token_ready = False
_progress_silenced = False

# 指数：显示名 → 东财符号（东财要求 sh000001 这种带交易所前缀的写法）
_INDEXES = {
    "上证指数": "sh000001",
    "深证成指": "sz399001",
    "创业板指": "sz399006",
    "沪深300": "sh000300",
    "中证500": "sh000905",
    "上证50": "sh000016",
    "科创50": "sh000688",
    "深证综指": "sz399106",
    "上证": "sh000001",
}


def _silence_progress_bar():
    """akshare 部分接口用 tqdm 刷进度条到 stderr，服务端日志里毫无意义，全局关掉。"""
    global _progress_silenced
    if _progress_silenced:
        return
    _progress_silenced = True
    try:
        from functools import partialmethod

        from tqdm import tqdm

        tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)
    except Exception:  # pragma: no cover - 屏蔽失败不影响取数
        pass


def _ak():
    """按需导入 akshare（体积较大，别拖慢服务启动）。"""
    global _akshare_mod
    if _akshare_mod is None:
        _silence_progress_bar()
        warnings.filterwarnings("ignore", module=r"akshare(\..*)?")
        import akshare

        _akshare_mod = akshare
    return _akshare_mod


def _tushare():
    """Tushare Pro 客户端。

    realtime_quote 走 require_permission → get_token()，读的是 ~/.tushare 下的凭据文件，
    不是 pro_api() 传进去的 token，所以必须先 set_token 落盘一次。
    """
    global _pro_client, _token_ready
    if not _token_ready:
        _token_ready = True
        if not TUSHARE_TOKEN:
            raise RuntimeError("未配置 TUSHARE_TOKEN，无法访问 Tushare 接口")
        ts.set_token(TUSHARE_TOKEN)
        _pro_client = ts.pro_api(TUSHARE_TOKEN)
    return _pro_client


def _cached(key: str, loader):
    """带 TTL 的进程内缓存。并发下可能重复加载一次，代价只是多打一个接口，可接受。"""
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1]
    df = loader()
    _cache[key] = (now, df)
    return df


def _to_ts_code(code: str) -> str:
    """600519 / sh600519 / 600519.SH → 600519.SH（Tushare 格式）"""
    s = (code or "").strip().upper()
    if not s or "." in s:
        return s
    if s[:2] in ("SH", "SZ", "BJ") and s[2:].isdigit():
        s = s[2:]
    if not s.isdigit():
        return s
    if s.startswith("920"):
        return f"{s}.BJ"
    if s.startswith(("6", "9")):
        return f"{s}.SH"
    if s.startswith(("4", "8")):
        return f"{s}.BJ"
    return f"{s}.SZ"


def _to_symbol(code: str) -> str:
    """600519.SH / sh600519 / 600519 → 600519（akshare/东财格式）"""
    s = (code or "").strip().upper()
    if "." in s:
        s = s.split(".", 1)[0]
    if s[:2] in ("SH", "SZ", "BJ") and s[2:].isdigit():
        s = s[2:]
    if s.isdigit() and len(s) < 6:
        s = s.zfill(6)
    return s


def _to_index_symbol(code: str) -> str:
    """上证指数 / 000001.SH / 000001 → sh000001（东财指数格式）"""
    s = (code or "").strip()
    if s in _INDEXES:
        return _INDEXES[s]
    u = s.upper()
    if "." in u:
        base, ex = u.split(".", 1)
        return f"{ex.lower()}{base}"
    if u[:2] in ("SH", "SZ", "BJ") and u[2:].isdigit():
        return u.lower()
    if u.isdigit() and len(u) == 6:
        if u.startswith("399"):
            return f"sz{u}"
        if u.startswith("899"):
            return f"bj{u}"
        return f"sh{u}"
    return u.lower()


def _index_display(symbol: str, fallback: str) -> str:
    for name, sym in _INDEXES.items():
        if sym == symbol:
            return name
    return fallback


def _fnum(value):
    """表格里的数值统一转 float；缺失/非数值/NaN/inf 都归 None，别让 nan 混进输出"""
    try:
        n = None if value is None else float(value)
    except (TypeError, ValueError):
        return None
    if n is None:
        return None
    return None if math.isnan(n) or math.isinf(n) else n


def _fmt(value, scale: float, unit: str, nd: int = 2) -> str:
    """按 scale 换算后带单位输出；值缺失/非法时给 —，别让整条工具失败"""
    n = _fnum(value)
    return "—" if n is None else f"{n / scale:.{nd}f}{unit}"


def _f2(value) -> str:
    n = _fnum(value)
    return "—" if n is None else f"{n:.2f}"


def _fdate(value) -> str:
    """20010827 / 2001-08-27 → 2001-08-27"""
    s = str(value if value is not None else "").split(".")[0].replace("-", "")
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return str(value) if value is not None else "—"


def _window(days: int) -> tuple[str, str]:
    """按交易日估算的自然日窗口（留一倍余量，再 head(days) 截断）"""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
    return start, end


@tool
def get_stock_info(stock_code: str) -> str:
    """获取股票基本信息：股票代码、名称、上市日期、所属行业、股本与市值。
    股票代码支持 600519 / 600519.SH / sh600519 几种写法"""
    try:
        symbol = _to_symbol(stock_code)
        df = _ak().stock_individual_info_em(symbol=symbol)
        if df is None or df.empty:
            return f"未找到股票代码 {stock_code} 的信息，请检查股票代码是否正确"

        kv = dict(zip(df["item"], df["value"]))
        result = (
            "股票基本信息：\n"
            f"股票代码：{kv.get('股票代码') or symbol}\n"
            f"股票名称：{kv.get('股票简称') or '—'}\n"
            f"上市日期：{_fdate(kv.get('上市时间'))}\n"
            f"所属行业：{kv.get('行业') or '—'}\n"
            f"总股本：{_fmt(kv.get('总股本'), 1e8, '亿股')}\n"
            f"流通股：{_fmt(kv.get('流通股'), 1e8, '亿股')}\n"
            f"总市值：{_fmt(kv.get('总市值'), 1e8, '亿元')}\n"
            f"流通市值：{_fmt(kv.get('流通市值'), 1e8, '亿元')}"
        )
        logger.info(f"[get_stock_info] 返回: {result}")
        return result
    except Exception as e:
        return f"获取股票信息失败：{str(e)}"


@tool
def get_stock_daily(stock_code: str, days: int = 30) -> str:
    """获取股票日线数据，包括开盘价、收盘价、最高价、最低价、成交量等"""
    try:
        ts_code = _to_ts_code(stock_code)
        start_date, end_date = _window(days)
        df = _tushare().daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            return f"未找到股票代码 {ts_code} 的日线数据"

        df = df.sort_values("trade_date", ascending=False).head(days)
        results = []
        for _, row in df.iterrows():
            date = datetime.strptime(str(row["trade_date"]), "%Y%m%d").strftime(
                "%Y-%m-%d"
            )
            results.append(
                f"{date}: 开盘={_f2(row['open'])}, 收盘={_f2(row['close'])}, "
                f"最高={_f2(row['high'])}, 最低={_f2(row['low'])}, "
                # vol=手、amount=千元（已与 akshare 同日数据核对）
                f"成交量={_fmt(row['vol'], 1e4, '万手')}, "
                f"成交额={_fmt(row['amount'], 1e5, '亿元')}"
            )

        result = f"股票 {ts_code} 最近{days}个交易日数据：\n\n" + "\n".join(results)
        logger.info(f"[get_stock_daily] 返回: {result}")
        return result
    except Exception as e:
        return f"获取股票日线数据失败：{str(e)}"


@tool
def get_stock_realtime(stock_code: str) -> str:
    """获取股票实时行情数据"""
    try:
        _tushare()  # 触发 set_token 落盘，realtime_quote 靠它读本地凭据
        ts_code = _to_ts_code(stock_code)
        df = ts.realtime_quote(ts_code=ts_code)
        if df is None or df.empty:
            return f"未找到股票代码 {ts_code} 的实时行情"

        info = df.iloc[0]
        price = _fnum(info.get("PRICE"))
        pre_close = _fnum(info.get("PRE_CLOSE"))
        if price is None:
            return f"未找到股票代码 {ts_code} 的实时行情"

        change = price - pre_close if pre_close else 0.0
        pct = change / pre_close * 100 if pre_close else 0.0
        result = (
            f"股票实时行情 - {info.get('NAME')} ({info.get('TS_CODE')})：\n"
            f"当前价格：{_f2(price)}\n"
            f"涨跌：{change:+.2f} ({pct:+.2f}%)\n"
            f"开盘：{_f2(info.get('OPEN'))}\n"
            f"最高：{_f2(info.get('HIGH'))}\n"
            f"最低：{_f2(info.get('LOW'))}\n"
            # VOLUME=股、AMOUNT=元（VOLUME×均价 ≡ AMOUNT 已验证）
            f"成交量：{_fmt(info.get('VOLUME'), 1e6, '万手')}\n"
            f"成交额：{_fmt(info.get('AMOUNT'), 1e8, '亿元')}\n"
            f"更新时间：{info.get('DATE')} {info.get('TIME')}"
        )
        logger.info(f"[get_stock_realtime] 返回: {result}")
        return result
    except Exception as e:
        return f"获取实时行情失败：{str(e)}"


@tool
def get_index_daily(index_code: str = "000001.SH", days: int = 30) -> str:
    """获取指数日线数据，如上证指数(000001.SH)、深证成指(399001.SZ)、沪深300(000300.SH)，
    也可以直接写「上证指数」「沪深300」这样的名称"""
    try:
        symbol = _to_index_symbol(index_code)
        # 东财单次返回全历史（约 0.9s），比 index_zh_a_hist 的分页（约 22s）快得多
        df = _ak().stock_zh_index_daily_em(symbol=symbol)
        if df is None or df.empty:
            return f"未找到指数 {index_code} 的日线数据"

        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        cut = pd.Timestamp(datetime.now() - timedelta(days=days * 2))
        df = (
            df[df["date"] >= cut]
            .sort_values("date", ascending=False)
            .head(days)
        )
        if df.empty:
            return f"未找到指数 {index_code} 的日线数据"

        results = []
        for _, row in df.iterrows():
            results.append(
                f"{row['date'].strftime('%Y-%m-%d')}: 开盘={_f2(row['open'])}, "
                f"收盘={_f2(row['close'])}, 最高={_f2(row['high'])}, "
                f"最低={_f2(row['low'])}, "
                f"成交量={_fmt(row['volume'], 1e8, '亿手')}, "
                f"成交额={_fmt(row['amount'], 1e8, '亿元')}"
            )

        name = _index_display(symbol, index_code)
        result = f"{name} 最近{days}个交易日数据：\n\n" + "\n".join(results)
        logger.info(f"[get_index_daily] 返回: {result}")
        return result
    except Exception as e:
        return f"获取指数日线数据失败：{str(e)}"


def _valuation(ak, symbol: str, indicator: str, days: int):
    """百度估值历史（列 date/value，市值单位亿元）。取不到返回 None，不拖垮整个工具。

    粒度要挑对：`近一年` 是逐日数据，`上市以来` 约每 15 天才一个采样点——
    默认优先后者会让绝大多数交易日 join 不上、整天显示 —。所以 365 天内一律先用逐日的。
    """
    periods = ("近一年", "上市以来") if days <= 365 else ("上市以来", "近一年")
    for period in periods:
        try:
            df = ak.stock_zh_valuation_baidu(
                symbol=symbol, indicator=indicator, period=period
            )
            if df is not None and not df.empty:
                return df
        except Exception:
            continue
    return None


@tool
def get_stock_daily_basic(stock_code: str, days: int = 30) -> str:
    """获取股票每日基本面指标，包括市盈率(TTM)、市净率、总市值、流通市值、换手率"""
    try:
        symbol = _to_symbol(stock_code)
        ak = _ak()
        start_date, end_date = _window(days)

        hist = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="",
        )
        if hist is None or hist.empty:
            return f"未找到股票代码 {stock_code} 的基本面数据"

        df = hist[["日期", "收盘", "换手率"]].copy()
        df["日期"] = pd.to_datetime(df["日期"])

        # 流通市值 = 总市值 × 流通股/总股本（百度没有流通市值序列）
        info = ak.stock_individual_info_em(symbol=symbol)
        kv = dict(zip(info["item"], info["value"]))
        total_share, float_share = _fnum(kv.get("总股本")), _fnum(kv.get("流通股"))
        float_ratio = float_share / total_share if total_share else None

        for indicator, col in (
            ("市盈率(TTM)", "市盈率(TTM)"),
            ("市净率", "市净率"),
            ("总市值", "总市值"),
        ):
            src = _valuation(ak, symbol, indicator, days)
            if src is None:
                continue
            src = src.copy()
            src["日期"] = pd.to_datetime(src["date"])
            df = df.merge(
                src[["日期", "value"]].rename(columns={"value": col}),
                on="日期",
                how="left",
            )

        df = df.sort_values("日期", ascending=False).head(days)
        results = []
        for _, row in df.iterrows():
            total_mv = _fnum(row.get("总市值"))  # 已是亿元
            circ_mv = (
                total_mv * float_ratio
                if total_mv is not None and float_ratio
                else None
            )
            results.append(
                f"{row['日期'].strftime('%Y-%m-%d')}: 收盘={_f2(row['收盘'])}, "
                f"换手率={_fmt(row.get('换手率'), 1, '%')}, "
                f"市盈率(TTM)={_fmt(row.get('市盈率(TTM)'), 1, '', 2)}, "
                f"市净率={_fmt(row.get('市净率'), 1, '', 2)}, "
                f"总市值={_fmt(total_mv, 1, '亿元')}, "
                f"流通市值={_fmt(circ_mv, 1, '亿元')}"
            )

        result = f"股票 {symbol} 最近{days}个交易日基本面数据：\n\n" + "\n".join(results)
        logger.info(f"[get_stock_daily_basic] 返回: {result}")
        return result
    except Exception as e:
        return f"获取基本面数据失败：{str(e)}"


def _search_by_industry(ak, keyword: str) -> str:
    """代码/名称没命中时退到行业板块：先精确匹配板块名，再前缀，最后模糊。"""
    boards = _cached("boards", lambda: ak.stock_board_industry_name_em())
    if boards is None or boards.empty:
        return f"未找到与「{keyword}」相关的股票"

    names = boards["板块名称"].astype(str)
    matched = boards[names == keyword]
    if matched.empty:
        matched = boards[names.str.startswith(keyword, na=False)]
    if matched.empty:
        matched = boards[names.str.contains(keyword, na=False, regex=False)]
    if matched.empty:
        return f"未找到与「{keyword}」相关的股票"

    board = str(matched.iloc[0]["板块名称"])
    try:
        cons = ak.stock_board_industry_cons_em(symbol=board)
    except Exception as e:
        return f"找到行业板块「{board}」，但获取成分股失败：{str(e)}"
    if cons is None or cons.empty:
        return f"行业板块「{board}」下没有成分股"

    lines = [
        f"{row['代码']} - {row['名称']}"
        for _, row in cons.head(30).iterrows()
    ]
    # 20 来只的板块要全给，否则像「白酒」这种会把茅台这类龙头截在前 10 之外
    note = f"共{len(cons)}只" if len(cons) <= 30 else f"共{len(cons)}只，展示前30"
    result = f"行业「{board}」成分股（{note}）：\n\n" + "\n".join(lines)
    logger.info(f"[search_stock] 返回: {result}")
    return result


@tool
def search_stock(keyword: str) -> str:
    """根据关键词搜索股票，支持股票代码、名称、行业"""
    try:
        kw = (keyword or "").strip()
        if not kw:
            return "请输入股票代码、名称或行业关键词"

        ak = _ak()
        listing = _cached("listing", lambda: ak.stock_info_a_code_name())
        if listing is not None and not listing.empty:
            hit = listing["code"].str.contains(kw, na=False, regex=False) | listing[
                "name"
            ].str.contains(kw, na=False, regex=False)
            hits = listing[hit]
            if not hits.empty:
                lines = [
                    f"{row['code']} - {row['name']}"
                    for _, row in hits.head(10).iterrows()
                ]
                result = f"搜索结果「{kw}」：\n\n" + "\n".join(lines)
                logger.info(f"[search_stock] 返回: {result}")
                return result

        return _search_by_industry(ak, kw)
    except Exception as e:
        return f"搜索股票失败：{str(e)}"
