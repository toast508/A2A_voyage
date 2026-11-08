import mysql.connector
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from mcp.server.fastmcp import FastMCP

from SmartVoyage.config import Config
from SmartVoyage.create_logger import logger
from SmartVoyage.utils.format import DateEncoder, default_encoder

conf = Config()

# 天气服务类
class WeatherService:  # 定义天气服务类，封装数据库操作逻辑
    def __init__(self):
        # 连接数据库
        self.conn = mysql.connector.connect(
            host=conf.host,
            port=conf.port,
            user=conf.user,
            password=conf.password,
            database=conf.database,
            # 每次查询都自动提交/结束事务，避免长期持有 REPEATABLE READ 快照导致读到旧数据
            autocommit=True
        )

    # 具体的查询方法：输出一个SQL字符串，输入一个格式化的json字符串
    def execute_query(self, sql: str) -> str:
        try:
            # 执行sql，获取数据
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute(sql)
            results = cursor.fetchall()
            cursor.close()

            # 格式化结果
            # print(f'results-->{results}')
            for result in results:  # 遍历每个结果字典
                for key, value in result.items():
                    if isinstance(value, (date, datetime, timedelta, Decimal)):  # 检查值是否为特殊类型
                        result[key] = default_encoder(value)  # 使用自定义编码器格式化该值
            # 序列化为JSON，如果有结果返回success，否则no_data；使用DateEncoder，非ASCII不转义
            return json.dumps({"status": "success", "data": results} if results else {"status": "no_data",
                                                                                      "message": "未找到天气数据，请确认城市和日期。"},
                              cls=DateEncoder, ensure_ascii=False)

        except Exception as e:
            logger.error(f'查询失败：{e}')
            # 返回错误JSON响应
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


# 创建天气MCP服务器
def create_weather_mcp_server():
    # 创建FastMCP实例
    weather_mcp = FastMCP(name="WeatherTools",
                          instructions="天气查询工具，基于 weather_data 表。",
                          log_level="ERROR",
                          host="127.0.0.1", port=8002)

    # 创建工具
    service = WeatherService()

    @weather_mcp.tool(
        name="query_weather",
        description="查询天气数据，输入 SQL，如 'SELECT * FROM weather_data WHERE city = \"北京\" AND fx_date = \"2025-07-30\"'"
    )
    def query_weather(sql: str) -> str:
        logger.info(f"执行天气查询: {sql}")
        return service.execute_query(sql)

    # 打印服务器信息
    logger.info("=== 天气MCP服务器信息 ===")
    logger.info(f"名称: {weather_mcp.name}")
    logger.info(f"描述: {weather_mcp.instructions}")

    # 运行服务器
    try:
        print("服务器已启动，请访问 http://127.0.0.1:8002/mcp")
        weather_mcp.run(transport="streamable-http")  # 使用 streamable-http 传输方式
    except Exception as e:
        print(f"服务器启动失败: {e}")


if __name__ == '__main__':
    # service = WeatherService()
    # sql = "SELECT * FROM weather_data WHERE city='上海' limit 2"
    # print(service.execute_query(sql))

    create_weather_mcp_server()