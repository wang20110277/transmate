import logging
from datetime import datetime, timedelta

import tushare as ts
from langchain_core.tools import tool

from app.core.config import TUSHARE_TOKEN

logger = logging.getLogger(__name__)


def get_pro_api():
    """Get Tushare Pro API instance"""
    pro = ts.pro_api(TUSHARE_TOKEN)
    return pro


@tool
def get_stock_info(stock_code: str) -> str:
    """获取股票基本信息，包括股票代码、名称、上市日期、行业等"""
    try:
        pro = get_pro_api()
        df = pro.stock_basic(
            ts_code=stock_code,
            fields="ts_code,symbol,name,area,industry,list_date,market,exchange",
        )
        if df.empty:
            result = f"未找到股票代码 {stock_code} 的信息，请检查股票代码是否正确"
            logger.info(f"[get_stock_info] 返回: {result}")
            return result

        info = df.iloc[0]
        result = (
            f"股票基本信息：\n"
            f"股票代码：{info['ts_code']}\n"
            f"股票名称：{info['name']}\n"
            f"上市日期：{info['list_date']}\n"
            f"所属板块：{info['area']}\n"
            f"所属行业：{info['industry']}\n"
            f"交易所：{info['exchange']}\n"
            f"市场类型：{info['market']}"
        )
        logger.info(f"[get_stock_info] 返回: {result}")
        return result
    except Exception as e:
        return f"获取股票信息失败：{str(e)}"


@tool
def get_stock_daily(stock_code: str, days: int = 30) -> str:
    """获取股票日线数据，包括开盘价、收盘价、最高价、最低价、成交量等"""
    try:
        pro = get_pro_api()
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

        df = pro.daily(ts_code=stock_code, start_date=start_date, end_date=end_date)
        if df.empty:
            result = f"未找到股票代码 {stock_code} 的日线数据"
            logger.info(f"[get_stock_daily] 返回: {result}")
            return result

        df = df.sort_values("trade_date", ascending=False).head(days)

        results = []
        for _, row in df.iterrows():
            date = datetime.strptime(str(row["trade_date"]), "%Y%m%d").strftime(
                "%Y-%m-%d"
            )
            results.append(
                f"{date}: 开盘={row['open']:.2f}, 收盘={row['close']:.2f}, "
                f"最高={row['high']:.2f}, 最低={row['low']:.2f}, "
                f"成交量={row['vol'] / 10000:.2f}万手, 成交额={row['amount'] / 100000000:.2f}亿元"
            )

        result = f"股票 {stock_code} 最近{days}个交易日数据：\n\n" + "\n".join(results)
        logger.info(f"[get_stock_daily] 返回: {result}")
        return result
    except Exception as e:
        return f"获取股票日线数据失败：{str(e)}"


@tool
def get_stock_realtime(stock_code: str) -> str:
    """获取股票实时行情数据"""
    try:
        df = ts.realtime_quote(ts_code=stock_code)
        if df.empty:
            result = f"未找到股票代码 {stock_code} 的实时行情"
            logger.info(f"[get_stock_realtime] 返回: {result}")
            return result

        info = df.iloc[0]
        result = (
            f"股票实时行情 - {info['name']} ({info['ts_code']})：\n"
            f"当前价格：{info['price']}\n"
            f"涨跌：{info['change']} ({info['pct_chg']}%)\n"
            f"开盘：{info['open']}\n"
            f"最高：{info['high']}\n"
            f"最低：{info['low']}\n"
            f"成交量：{info['vol'] / 10000:.2f}万手\n"
            f"成交额：{info['amount'] / 100000000:.2f}亿元\n"
            f"更新时间：{info['time']}"
        )
        logger.info(f"[get_stock_realtime] 返回: {result}")
        return result
    except Exception as e:
        return f"获取实时行情失败：{str(e)}"


@tool
def get_index_daily(index_code: str = "000001.SH", days: int = 30) -> str:
    """获取指数日线数据，如上证指数(000001.SH)、深证成指(399001.SZ)等"""
    try:
        pro = get_pro_api()
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

        df = pro.index_daily(
            ts_code=index_code, start_date=start_date, end_date=end_date
        )
        if df.empty:
            result = f"未找到指数 {index_code} 的日线数据"
            logger.info(f"[get_index_daily] 返回: {result}")
            return result

        df = df.sort_values("trade_date", ascending=False).head(days)

        results = []
        for _, row in df.iterrows():
            date = datetime.strptime(str(row["trade_date"]), "%Y%m%d").strftime(
                "%Y-%m-%d"
            )
            results.append(
                f"{date}: 开盘={row['open']:.2f}, 收盘={row['close']:.2f}, "
                f"最高={row['high']:.2f}, 最低={row['low']:.2f}, "
                f"成交量={row['vol'] / 100000000:.2f}亿手"
            )

        index_name = {
            "000001.SH": "上证指数",
            "399001.SZ": "深证成指",
            "399006.SZ": "创业板指",
        }.get(index_code, index_code)
        result = f"{index_name} 最近{days}个交易日数据：\n\n" + "\n".join(results)
        logger.info(f"[get_index_daily] 返回: {result}")
        return result
    except Exception as e:
        return f"获取指数日线数据失败：{str(e)}"


@tool
def get_stock_daily_basic(stock_code: str, days: int = 30) -> str:
    """获取股票每日基本面指标，包括总市值、流通市值、市盈率、市净率等"""
    try:
        pro = get_pro_api()
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

        df = pro.daily_basic(
            ts_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            fields="trade_date,ts_code,close,turnover_rate,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_share,float_share,free_share,total_mv,circ_mv",
        )
        if df.empty:
            result = f"未找到股票代码 {stock_code} 的基本面数据"
            logger.info(f"[get_stock_daily_basic] 返回: {result}")
            return result

        df = df.sort_values("trade_date", ascending=False).head(days)

        results = []
        for _, row in df.iterrows():
            date = datetime.strptime(str(row["trade_date"]), "%Y%m%d").strftime(
                "%Y-%m-%d"
            )
            results.append(
                f"{date}: 收盘={row['close']:.2f}, 换手率={row['turnover_rate']:.2f}%, "
                f"市盈率(TTM)={row['pe_ttm']:.2f}, 市净率={row['pb']:.2f}, "
                f"总市值={row['total_mv'] / 100000000:.2f}亿, 流通市值={row['circ_mv'] / 100000000:.2f}亿"
            )

        result = f"股票 {stock_code} 最近{days}个交易日基本面数据：\n\n" + "\n".join(
            results
        )
        logger.info(f"[get_stock_daily_basic] 返回: {result}")
        return result
    except Exception as e:
        return f"获取基本面数据失败：{str(e)}"


@tool
def search_stock(keyword: str) -> str:
    """根据关键词搜索股票，支持股票代码、名称、行业等"""
    try:
        pro = get_pro_api()
        df = pro.stock_basic(
            list_status="L", fields="ts_code,symbol,name,area,industry,market"
        )

        if not df.empty:
            mask = (
                df["ts_code"].str.contains(keyword, na=False)
                | df["name"].str.contains(keyword, na=False)
                | df["industry"].str.contains(keyword, na=False)
            )
            df = df[mask]

        if df.empty:
            result = f"未找到与「{keyword}」相关的股票"
            logger.info(f"[search_stock] 返回: {result}")
            return result

        df = df.head(10)
        results = []
        for _, row in df.iterrows():
            results.append(
                f"{row['ts_code']} - {row['name']} | 行业: {row['industry']} | 板块: {row['area']}"
            )

        result = f"搜索结果「{keyword}」：\n\n" + "\n".join(results)
        logger.info(f"[search_stock] 返回: {result}")
        return result
    except Exception as e:
        return f"搜索股票失败：{str(e)}"
