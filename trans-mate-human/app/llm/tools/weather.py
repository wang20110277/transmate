import httpx
from langchain_core.tools import tool


@tool
async def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    city_coords = {
        "北京": (39.9042, 116.4074),
        "上海": (31.2304, 121.4737),
        "广州": (23.1291, 113.2644),
        "深圳": (22.5431, 114.0579),
        "杭州": (30.2741, 120.1551),
        "成都": (30.5728, 104.0668),
        "重庆": (29.4316, 106.9123),
        "武汉": (30.5928, 114.3055),
        "西安": (34.3416, 108.9398),
        "南京": (32.0603, 118.7969),
        "天津": (39.3434, 117.3616),
        "苏州": (31.2989, 120.5853),
        "郑州": (34.7466, 113.6253),
        "长沙": (28.2282, 112.9388),
        "青岛": (36.0671, 120.3826),
        "沈阳": (41.8057, 123.4315),
        "大连": (38.9140, 121.6147),
        "厦门": (24.4798, 118.0894),
        "昆明": (25.0406, 102.7129),
        "哈尔滨": (45.8038, 126.5340),
    }
    
    lat, lon = city_coords.get(city, (39.9042, 116.4074))
    
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m",
        "timezone": "Asia/Shanghai"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
        current = data.get("current", {})
        temp = current.get("temperature_2m", "N/A")
        humidity = current.get("relative_humidity_2m", "N/A")
        wind = current.get("wind_speed_10m", "N/A")
        weather_code = current.get("weather_code", 0)
        
        weather_descriptions = {
            0: "晴", 1: "晴间多云", 2: "多云", 3: "阴",
            45: "雾", 48: "雾凇",
            51: "小毛毛雨", 53: "中毛毛雨", 55: "大毛毛雨",
            61: "小雨", 63: "中雨", 65: "大雨",
            71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
            80: "小阵雨", 81: "中阵雨", 82: "大阵雨",
            85: "小阵雪", 86: "大阵雪",
            95: "雷暴", 96: "雷暴伴冰雹", 99: "强雷暴伴冰雹",
        }
        weather_desc = weather_descriptions.get(weather_code, "未知")
        
        return f"{city}当前天气：{weather_desc}，温度：{temp}°C，湿度：{humidity}%，风速：{wind}km/h"
        
    except httpx.TimeoutException:
        return f"获取{city}天气超时，请稍后重试"
    except httpx.HTTPStatusError as e:
        return f"获取{city}天气失败：HTTP错误 {e.response.status_code}"
    except Exception as e:
        return f"获取{city}天气失败：{str(e)}"
