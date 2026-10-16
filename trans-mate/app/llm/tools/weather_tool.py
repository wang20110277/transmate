"""天气查询：和风天气（QWeather）。

和风已停用公共域名 api/devapi/geoapi.qweather.com，必须用账号专属的 API Host，
且 API Host 本身也是认证要素之一——所以 Host 和 KEY 都从 .env 读，缺一个都请求不到。

链路：GeoAPI 把城市名解析成 LocationID → 查实况 → 查 3 天预报（预报失败不影响实况）。
城市名统一交给 GeoAPI 解析，不再像旧版那样写死 20 个城市、查不到就静默回退北京坐标。
"""

import httpx
from langchain_core.tools import tool

from app.core.config import QWEATHER_API_HOST, QWEATHER_API_KEY

_TIMEOUT = 10.0

# 和风 200 响应里也可能带非 200 的业务码
_QW_ERRORS = {
    "204": "查询成功但无数据",
    "400": "请求参数错误",
    "401": "认证失败，请确认 API Host 与 API KEY 属于同一账号",
    "402": "超出访问次数或余额不足",
    "403": "无访问权限（该 API 未开通）",
    "404": "查询的数据或地区不存在",
    "405": "超过访问限制",
    "408": "请求过于频繁",
    "409": "服务异常",
    "500": "服务端错误",
}


class QWeatherError(RuntimeError):
    """和风 HTTP 层错误（非 2xx，响应是 RFC7807 problem+json）"""


def _describe(code) -> str:
    return _QW_ERRORS.get(str(code), f"和风天气返回异常码 {code}")


def _problem_detail(response: httpx.Response) -> str:
    """从 problem+json 里取可读原因，取不到就退回状态码"""
    try:
        problem = response.json().get("error", {}) or {}
    except Exception:
        problem = {}
    title, detail = problem.get("title") or "", problem.get("detail") or ""
    if detail and title:
        return f"{title}：{detail}"
    return detail or title or f"HTTP {response.status_code}"


async def _get(path: str, params: dict) -> dict:
    """带 API KEY 的 GET。非 2xx 抛 QWeatherError，成功返回和风 JSON（可能仍含非 200 的业务码）。"""
    url = f"https://{QWEATHER_API_HOST}{path}"
    headers = {"X-QW-Api-Key": QWEATHER_API_KEY, "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(url, params=params, headers=headers)
    if response.status_code >= 400:
        raise QWeatherError(_problem_detail(response))
    return response.json()


def _plausible(query: str, name: str) -> bool:
    """校验 GeoAPI 的匹配是否像话。

    实测 GeoAPI 对中文垃圾输入会返回 200 并匹配到毫不相干的海外城市
    （「不存在的城市xyz」→ 日本安城市），只有纯 ASCII 乱码才老老实实报 400。
    这道校验只对含中文的查询生效，拉丁查询（英文城市名/adcode）仍交给 GeoAPI 自己判断。
    """
    if not any("\u4e00" <= ch <= "\u9fff" for ch in query):
        return True
    if not name:
        return False
    return name[0] == query[0] or name in query or query in name


@tool
async def get_weather(city: str) -> str:
    """获取指定城市的天气信息：当前实况与未来三天预报"""
    if not QWEATHER_API_HOST or not QWEATHER_API_KEY:
        return "天气功能未配置，请联系管理员设置 QWEATHER_API_HOST 与 QWEATHER_API_KEY"

    name = (city or "").strip()
    if not name:
        return "请提供要查询的城市名"

    try:
        try:
            geo = await _get("/geo/v2/city/lookup", {"location": name, "lang": "zh"})
        except QWeatherError as e:
            return f"未找到城市「{name}」：{e}"

        candidates = geo.get("location") or []
        if not candidates:
            return f"未找到城市「{name}」：和风天气未返回匹配结果"

        picked = next(
            (item for item in candidates if _plausible(name, str(item.get("name", "")))),
            None,
        )
        if picked is None:
            tried = "、".join(str(item.get("name", "")) for item in candidates[:3])
            return f"未找到城市「{name}」：最接近的匹配是「{tried}」，请确认城市名"

        loc_id, actual_name = picked["id"], picked.get("name") or name

        now_data = await _get("/v7/weather/now", {"location": loc_id, "lang": "zh"})
        if str(now_data.get("code")) != "200":
            return f"获取{actual_name}实时天气失败：{_describe(now_data.get('code'))}"
        now = now_data.get("now") or {}

        lines = [
            f"{actual_name}天气（更新于 {now_data.get('updateTime', '—')}）",
            "",
            f"当前：{now.get('text', '—')} {now.get('temp', '—')}°C"
            f"（体感 {now.get('feelsLike', '—')}°C），"
            f"湿度 {now.get('humidity', '—')}%，"
            f"{now.get('windDir', '—')}{now.get('windScale', '—')}级"
            f"（{now.get('windSpeed', '—')}km/h），"
            f"降水 {now.get('precip', '—')}mm",
        ]

        # 预报拿不到不该影响实况返回
        try:
            daily_data = await _get("/v7/weather/3d", {"location": loc_id, "lang": "zh"})
        except Exception:
            daily_data = {}
        if str(daily_data.get("code")) == "200":
            labels = ("今日", "明日", "后日")
            for i, day in enumerate(daily_data.get("daily", [])[:3]):
                label = labels[i] if i < len(labels) else str(day.get("fxDate", ""))
                lines.append(
                    f"{label}({day.get('fxDate', '—')}) "
                    f"{day.get('tempMin', '—')}~{day.get('tempMax', '—')}°C "
                    f"白天{day.get('textDay', '—')}/夜间{day.get('textNight', '—')}"
                )

        return "\n".join(lines)

    except httpx.TimeoutException:
        return f"获取{name}天气超时，请稍后重试"
    except QWeatherError as e:
        return f"获取{name}天气失败：{e}"
    except Exception as e:
        return f"获取{name}天气失败：{str(e)}"
