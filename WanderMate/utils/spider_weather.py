import requests
import mysql.connector
from datetime import datetime, timedelta
import schedule  # 用来做调度的
import time
import json
import gzip
import pytz  # 用来设置时区
from WanderMate.config import Config

conf = Config()

# 配置
API_KEY = "59f67e5e75c94a4a84d08c72d6ad2208"
city_codes = {
    "北京": "101010100",
    "上海": "101020100",
    "广州": "101280101",
    "深圳": "101280601"
}
BASE_URL = "https://mx759fujby.re.qweatherapi.com/v7/weather/30d"
TZ = pytz.timezone('Asia/Shanghai')  # 使用上海时区

# MySQL 配置
db_config = {
    "host": conf.host,
    "user": conf.user,
    "password": conf.password,
    "database": conf.database,
    "charset": "utf8mb4"
}

# 连接数据库
def connect_db():
    return mysql.connector.connect(**db_config)

# 爬取数据（30天）
def fetch_weather_data(city, location):
    headers = {
        "X-QW-Api-Key": API_KEY,
        "Accept-Encoding": "gzip"
    }
    url = f"{BASE_URL}?location={location}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        if response.headers.get('Content-Encoding') == 'gzip':
            data = gzip.decompress(response.content).decode('utf-8')
        else:
            data = response.text
        return json.loads(data)
    except requests.RequestException as e:
        print(f"请求 {city} 天气数据失败: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"{city} JSON 解析错误: {e}, 响应内容: {response.text[:500]}...")
        return None
    except gzip.BadGzipFile:
        print(f"{city} 数据未正确解压，尝试直接解析: {response.text[:500]}...")
        return json.loads(response.text) if response.text else None

# 查询数据库中指定城市的最新更新时间
def get_latest_update_time(cursor, city):
    cursor.execute("SELECT MAX(update_time) FROM weather_data WHERE city = %s", (city,))
    result = cursor.fetchone()
    # print("最新更新时间:", result)  # 最新更新时间: (datetime.datetime(2025, 8, 11, 20, 18),)
    return result[0] if result[0] else None

# 判断是否需要更新城市天气数据
def should_update_data(latest_time, force_update=False):
    if force_update:
        return True
    if latest_time is None:
        return True

    # 时区问题：确保 latest_time 有时区信息
    if latest_time and latest_time.tzinfo is None:
        latest_time = latest_time.replace(tzinfo=TZ)

    current_time = datetime.now(TZ)
    return (current_time - latest_time) > timedelta(days=1)

# 写入或更新天气预报数据到数据库
def store_weather_data(conn, cursor, city, data):
    if not data or data.get("code") != "200":
        print(f"{city} 数据无效，跳过存储。")
        return

    daily_data = data.get("daily", [])
    update_time = datetime.fromisoformat(data.get("updateTime").replace("+08:00", "+08:00")).replace(tzinfo=TZ)

    for day in daily_data:
        fx_date = datetime.strptime(day["fxDate"], "%Y-%m-%d").date()
        values = (
            city, fx_date,
            day.get("sunrise"), day.get("sunset"),
            day.get("moonrise"), day.get("moonset"),
            day.get("moonPhase"), day.get("moonPhaseIcon"),
            day.get("tempMax"), day.get("tempMin"),
            day.get("iconDay"), day.get("textDay"),
            day.get("iconNight"), day.get("textNight"),
            day.get("wind360Day"), day.get("windDirDay"), day.get("windScaleDay"), day.get("windSpeedDay"),
            day.get("wind360Night"), day.get("windDirNight"), day.get("windScaleNight"), day.get("windSpeedNight"),
            day.get("precip"), day.get("uvIndex"),
            day.get("humidity"), day.get("pressure"),
            day.get("vis"), day.get("cloud"),
            update_time
        )
        insert_query = """
        INSERT INTO weather_data (
            city, fx_date, sunrise, sunset, moonrise, moonset, moon_phase, moon_phase_icon,
            temp_max, temp_min, icon_day, text_day, icon_night, text_night,
            wind360_day, wind_dir_day, wind_scale_day, wind_speed_day,
            wind360_night, wind_dir_night, wind_scale_night, wind_speed_night,
            precip, uv_index, humidity, pressure, vis, cloud, update_time
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            sunrise = VALUES(sunrise), sunset = VALUES(sunset), moonrise = VALUES(moonrise),
            moonset = VALUES(moonset), moon_phase = VALUES(moon_phase), moon_phase_icon = VALUES(moon_phase_icon),
            temp_max = VALUES(temp_max), temp_min = VALUES(temp_min), icon_day = VALUES(icon_day),
            text_day = VALUES(text_day), icon_night = VALUES(icon_night), text_night = VALUES(text_night),
            wind360_day = VALUES(wind360_day), wind_dir_day = VALUES(wind_dir_day), wind_scale_day = VALUES(wind_scale_day),
            wind_speed_day = VALUES(wind_speed_day), wind360_night = VALUES(wind360_night),
            wind_dir_night = VALUES(wind_dir_night), wind_scale_night = VALUES(wind_scale_night),
            wind_speed_night = VALUES(wind_speed_night), precip = VALUES(precip), uv_index = VALUES(uv_index),
            humidity = VALUES(humidity), pressure = VALUES(pressure), vis = VALUES(vis),
            cloud = VALUES(cloud), update_time = VALUES(update_time)
        """
        try:
            cursor.execute(insert_query, values)
            print(f"{city} {fx_date} 数据写入/更新成功: {day.get('textDay')}, 影响行数: {cursor.rowcount}")

            conn.commit()
            print(f"{city} 事务提交完成。")
        except mysql.connector.Error as e:
            print(f"{city} {fx_date} 数据库错误: {e}")
            conn.rollback()
            print(f"{city} 事务回滚。")

# 更新所有城市数据
def update_weather(force_update=False):
    conn = connect_db()
    cursor = conn.cursor()

    for city, location in city_codes.items():
        latest_time = get_latest_update_time(cursor, city)
        if should_update_data(latest_time, force_update):
            print(f"开始更新 {city} 天气数据...")
            data = fetch_weather_data(city, location)
            if data:
                store_weather_data(conn, cursor, city, data)
        else:
            print(f"{city} 数据已为最新，无需更新。最新更新时间: {latest_time}")

    cursor.close()
    conn.close()

# 设置定时任务，每天在 PDT 16:00（北京时间 01:00）调用 update_weather 函数
def setup_scheduler():
    # 北京时间 1:00 对应 PDT 前一天的 16:00（夏令时）【相当于定了一个闹铃，在凌晨1点执行update_weather任务】
    schedule.every().day.at("16:00").do(update_weather)

    while True:  # 用死循环去检查，是否是到点了！
        schedule.run_pending()
        time.sleep(60)
        print("正在检查任务...")


if __name__ == '__main__':
    # todo: 1.测试数据库连接
    # conn = connect_db()
    # print(conn.is_connected())
    # print('数据库连接成功')
    # conn.close()

    # todo: 2.测试数据爬取
    # weather_data = fetch_weather_data("北京", city_codes["北京"])
    # print(weather_data)
    # print("解析成功！")

    # todo: 3.测试获取最新更新时间
    # # 建立数据库连接
    # conn = connect_db()
    # cursor = conn.cursor()
    # # 获取北京城市的最新更新的时间日期
    # print(get_latest_update_time(cursor, '北京'))
    # # 关闭数据库连接
    # cursor.close()
    # conn.close()

    # todo: 4.测试判断是否需要更新数据
    # from datetime import datetime, timedelta
    # import pytz
    #
    # # 设置时区
    # TZ = pytz.timezone('Asia/Shanghai')
    #
    # # 模拟一个2天前的更新时间
    # latest = datetime.now(TZ) - timedelta(days=2)
    # print("========模拟一个两天前的时间==============")
    # print(latest)
    # # 测试是否需要更新数据
    # print(should_update_data(latest))
    #
    # # 根据更新判断结果输出相应信息
    # if should_update_data(latest):
    #     print(f"需要更新数据，上次更新时间：{latest}")
    # else:
    #     print("没有数据，需要更新数据！")

    # todo: 5.测试写入或更新数据
    # conn = connect_db()
    # cursor = conn.cursor()
    # data = fetch_weather_data("北京", "101010100")
    # store_weather_data(conn, cursor, "北京", data)
    # print("数据存储完成。")

    # todo: 6.测试更新所有数据
    # update_weather()

    # todo: 7.启动定时任务
    setup_scheduler()