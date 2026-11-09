# SmartVoyage · 基于 A2A 与 MCP 的旅行智能助手

SmartVoyage 是一个多智能体旅行助手：客户端先用大模型识别用户意图，再通过 **A2A（Agent2Agent）** 协议把任务分发给天气、票务查询、票务预定三个智能体；智能体通过 **MCP（Model Context Protocol）** 工具服务访问 MySQL，最终由大模型把数据库结果整理成自然语言回答。

> 支持天气查询、火车票 / 机票 / 演唱会票查询、票务预定（演示）和景点推荐，提供 Streamlit 网页端与命令行两种入口。

---

## 功能特性

- **多意图识别**：一次提问可同时识别 `weather`、`flight`、`train`、`concert`、`order`、`attraction`，并分别路由。
- **多轮对话**：保留最近若干轮上下文，支持“那后天呢”这类追问。
- **信息不足时主动追问**：缺少城市、日期等必要条件时返回追问，而不是编造参数。
- **A2A 智能体网络**：三个独立 Agent 服务分别监听 5005 / 5006 / 5007。
- **MCP 工具服务**：将数据库查询和预定动作封装成标准 MCP 工具，通过 streamable-http 暴露。
- **基于表结构的 SQL 生成**：Prompt 中内置建表语句，模型只生成 `SELECT` 查询。
- **数据库结果驱动回答**：查询结果以 JSON 返回给上层 Agent，再由大模型总结，减少凭空编造。
- **双客户端**：Streamlit 网页界面与命令行交互。
- **Agent 状态展示**：网页右侧显示各智能体在线 / 离线状态、技能与地址。
- **日志记录**：统一写入 `SmartVoyage/logs/app.log`，便于排查链路问题。

---

## 系统架构

```text
用户
 ├─ Streamlit 网页端  SmartVoyage/app.py
 └─ 命令行客户端      SmartVoyage/main.py
          │
          │ ① 意图识别 + 问题改写（LangChain + LLM）
          ▼
   A2A 智能体网络
   ├─ WeatherQueryAssistant  :5005 ──MCP──> WeatherTools :8002 ──> MySQL weather_data
   ├─ TicketQueryAssistant   :5006 ──MCP──> TicketTools  :8001 ──> MySQL train/flight/concert_tickets
   └─ TicketOrderAssistant   :5007 ──MCP──> OrderTools   :8003 ──> 演示预定（不写数据库）
```

一次查询的完整链路：

1. 客户端把用户问题交给意图识别模型，得到 JSON：`intents`、`user_queries`、`follow_up_message`。
2. 按意图选择 A2A Agent，并把改写后的问题作为 Task 发送过去。
3. A2A Agent 根据内置表结构生成 SQL，通过 MCP 客户端调用对应工具。
4. MCP 服务执行 SQL，把结果格式化为 JSON 返回。
5. 天气 / 票务 Agent 再把 JSON 交给总结模型生成回答；预定 Agent 直接返回执行结果。
6. 客户端展示回答，并写入对话历史。

### 服务与端口

| 服务 | 启动模块 | 端口 | 说明 |
| --- | --- | --- | --- |
| 票务查询 MCP | `SmartVoyage.mcp_server.mcp_ticket_server` | 8001 | 工具 `query_tickets` |
| 天气查询 MCP | `SmartVoyage.mcp_server.mcp_weather_server` | 8002 | 工具 `query_weather` |
| 票务预定 MCP | `SmartVoyage.mcp_server.mcp_order_server` | 8003 | 工具 `order_train`、`order_flight`、`order_concert` |
| 天气 Agent | `SmartVoyage.a2a_server.weather_server` | 5005 | `WeatherQueryAssistant` |
| 票务查询 Agent | `SmartVoyage.a2a_server.ticket_server` | 5006 | `TicketQueryAssistant` |
| 票务预定 Agent | `SmartVoyage.a2a_server.order_server` | 5007 | `TicketOrderAssistant` |
| 网页客户端 | `streamlit run SmartVoyage/app.py` | 8501 | Streamlit 默认端口 |
| 命令行客户端 | `python -m SmartVoyage.main` | — | 终端交互 |

> 预定 MCP 目前是演示实现：记录日志并返回“预定成功”，不会真正写库或调用支付接口。

---

## 技术栈与开源项目

项目基于以下维护活跃的开源项目构建，版本以 `smart_voyage_requirements.txt` 锁定为准。

| 开源项目 | 在项目中的用途 | 仓库 |
| --- | --- | --- |
| **python-a2a** | A2A 服务端 / 客户端、`AgentNetwork`、`AgentCard`、Task 生命周期 | <https://github.com/themanojdesai/python-a2a> |
| **MCP Python SDK** | `FastMCP` 工具服务、`streamable-http` 传输 | <https://github.com/modelcontextprotocol/python-sdk> |
| **LangChain** | 意图识别、SQL 生成 Prompt、结果总结、Tool Calling Agent | <https://github.com/langchain-ai/langchain> |
| **LangChain MCP Adapters** | 把 MCP 工具加载为 LangChain tools，供预定 Agent 调用 | <https://github.com/langchain-ai/langchain-mcp-adapters> |
| **Streamlit** | 网页对话界面 | <https://github.com/streamlit/streamlit> |
| **MySQL Connector/Python** | 连接 MySQL、执行查询 | <https://github.com/mysql/mysql-connector-python> |
| **python-dotenv** | 从项目根目录 `.env` 读取配置 | <https://github.com/theskumar/python-dotenv> |
| **schedule** | 天气数据每日定时更新 | <https://github.com/dbader/schedule> |

大模型通过 LangChain 的 `ChatOpenAI` 兼容接口调用，默认使用 DeepSeek：

```text
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL_NAME=deepseek-chat
```

---

## 快速开始

### 1. 环境要求

| 依赖 | 要求 |
| --- | --- |
| Python | 3.11 及以上 |
| MySQL | 8.x，默认连接端口 `3307`（可在 `.env` 修改） |
| 大模型 | 一个 OpenAI 兼容接口的 API Key（默认 DeepSeek） |

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows CMD
.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate
```

```bash
pip install -r smart_voyage_requirements.txt
```

国内网络可换用镜像：

```bash
pip install -r smart_voyage_requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> `smart_voyage_requirements.txt` 是完整环境导出，包含 `torch`、`transformers` 等较大的包，安装时间会较长。

### 3. 配置 `.env`

在项目根目录创建 `.env`：

```dotenv
# 大模型
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL_NAME=deepseek-chat

# MySQL
DB_HOST=127.0.0.1
DB_PORT=3307
DB_USER=root
DB_PASSWORD=your-password
DB_DATABASE=travel_rag
```

配置由 `SmartVoyage/config.py` 中的 `load_dotenv()` 自动加载，字段含义见[配置说明](#配置说明)。

> `.env` 含密钥和数据库密码，不要提交到公开仓库；同时请确认它已被 `.gitignore` 忽略。

### 4. 初始化数据库

```bash
mysql -u root -p -h 127.0.0.1 -P 3307 < SmartVoyage/sql/create_table.sql
mysql -u root -p -h 127.0.0.1 -P 3307 < SmartVoyage/sql/insert_data.sql
```

`create_table.sql` 会先执行 `DROP DATABASE IF EXISTS travel_rag` 再重建，**已有同名数据库时请先备份**。

验证：

```bash
mysql -u root -p -h 127.0.0.1 -P 3307 -e "USE travel_rag; SHOW TABLES;"
```

预期能看到 4 张表：

```text
concert_tickets
flight_tickets
train_tickets
weather_data
```

`insert_data.sql` 会把示例票务和天气日期整体平移到“当前日期”附近，方便直接查询“明天 / 后天”的数据。

### 5. 启动服务

必须先启动 MCP 服务，再启动 A2A Agent，最后启动客户端。每个服务单独占用一个终端。

**终端 1–3：启动 MCP 工具服务**

```bash
# 票务查询 :8001 / 天气查询 :8002 / 票务预定 :8003
python -m SmartVoyage.mcp_server.mcp_ticket_server
python -m SmartVoyage.mcp_server.mcp_weather_server
python -m SmartVoyage.mcp_server.mcp_order_server
```

票务 MCP 启动后预期输出：`服务器已启动，请访问 http://127.0.0.1:8001/mcp`。

**终端 4–6：启动 A2A 智能体**

```bash
# 天气 :5005 / 票务查询 :5006 / 票务预定 :5007
python -m SmartVoyage.a2a_server.weather_server
python -m SmartVoyage.a2a_server.ticket_server
python -m SmartVoyage.a2a_server.order_server
```

**终端 7：启动客户端**

```bash
# 网页端：预期浏览器打开 http://localhost:8501
streamlit run SmartVoyage/app.py

# 或命令行端
python -m SmartVoyage.main
```

网页端左侧为对话区，右侧为 Agent Network 状态与卡片。

---

## 使用示例

### 网页端

打开 `http://localhost:8501` 后，在底部输入框提问即可。右侧会显示天气、票务、预订三个智能体的在线状态。

| 输入 | 识别意图 | 路由与预期结果 |
| --- | --- | --- |
| `明天上海天气怎么样？` | `weather` | 路由到 `WeatherQueryAssistant`，返回城市、日期、温度、天气描述、湿度等总结 |
| `查询明天从上海到北京的机票` | `flight` | 路由到 `TicketQueryAssistant`，返回航班号、时间、舱位、价格、余票 |
| `北京到上海 2025-11-15 火车票 二等座 1张` | `order` | 路由到 `TicketOrderAssistant`，返回预定成功提示（演示） |
| `帮我推荐北京 3 个必去景点` | `attraction` | 不调用 Agent，由大模型直接生成 3–5 个景点建议 |
| `查广州到深圳的车次和天气` | `train` + `weather` | 同时调用票务与天气 Agent，两段结果以空行拼接 |
| `北京天气` | `weather` | 缺少日期时返回追问，例如“请提供具体的需要查询的日期” |

> 查询结果依赖数据库中的实际数据。若返回“未找到数据”，请先确认城市、日期和座位类型是否在 `insert_data.sql` 的示例范围内。

### 命令行端

```bash
python -m SmartVoyage.main
```

启动后预期看到：

```text
🤖 基于A2A的SmartVoyage旅行智能助手
欢迎体验智能对话！输入问题，按回车提交；输入'quit'退出；输入'cards'查看代理卡片。

🛠️ Agent Cards:

--- Agent: WeatherQueryAssistant ---
技能: [...]
描述: 基于LangChain提供天气查询服务的助手
地址: http://localhost:5005
状态: 在线
```

输入问题后：

```text
请输入您的问题: 明天上海天气怎么样？
正在分析您的意图...

助手回复：
根据最新数据，上海明天的天气预报为……
```

输入 `cards` 可重新查看智能体卡片，输入 `quit` 退出。

### 直接测试 MCP 工具

先启动票务 MCP 服务，再运行联调脚本：

```bash
python -m SmartVoyage.test.test_ticket_mcp_server
```

预期输出包含：

```text
会话初始化成功，可以开始调用工具。
tools-->[...]
机票查询结果：...
火车票查询结果：...
演唱会票查询结果：...
```

`SmartVoyage/test/` 下还提供了天气 MCP、预定 MCP、三个 A2A Agent 的联调脚本，可按同样方式运行。

---

## 配置说明

### 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 无 | 大模型 API Key，必填 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容接口地址 |
| `DEEPSEEK_MODEL_NAME` | `deepseek-chat` | 模型名称 |
| `DB_HOST` | `localhost` | MySQL 主机 |
| `DB_PORT` | `3307` | MySQL 端口 |
| `DB_USER` | `root` | MySQL 用户名 |
| `DB_PASSWORD` | 无 | MySQL 密码 |
| `DB_DATABASE` | `travel_rag` | 数据库名 |

配置读取逻辑在 `SmartVoyage/config.py`；日志文件固定为 `SmartVoyage/logs/app.log`。

### 数据表

| 表名 | 内容 | 使用方 |
| --- | --- | --- |
| `weather_data` | 城市逐日天气：温度、天气描述、湿度、风向、降水等 | 天气 MCP / 天气 Agent |
| `train_tickets` | 火车票：出发/到达城市、时间、车次、座位类型、余票、价格 | 票务 MCP / 票务 Agent |
| `flight_tickets` | 机票：出发/到达城市、时间、航班号、舱位、余票、价格 | 票务 MCP / 票务 Agent |
| `concert_tickets` | 演唱会票：艺人、城市、场馆、时间、票类型、余票、价格 | 票务 MCP / 票务 Agent |

### 天气数据定时更新（可选）

`SmartVoyage/utils/spider_weather.py` 会调用和风天气 30 天预报接口，更新北京、上海、广州、深圳四个城市的数据，并启动每日 `16:00` 的定时任务（按运行环境本地时间；代码注释按 PDT 说明）：

```bash
python -m SmartVoyage.utils.spider_weather
```

> 该脚本启动后会进入常驻循环。脚本内的天气 API Key 与数据库连接参数为文件内配置；如需长期使用，请替换为自己的 Key，并补充读取 `DB_PORT`（当前连接配置未显式传入端口）。

### 修改端口

端口目前硬编码在各自模块中：

- MCP：`mcp_ticket_server.py`（8001）、`mcp_weather_server.py`（8002）、`mcp_order_server.py`（8003）
- A2A：`weather_server.py`（5005）、`ticket_server.py`（5006）、`order_server.py`（5007）
- 客户端：`app.py` / `main.py` 中的 `agent_urls`

修改时需同时更新“服务端监听端口”和“调用方 URL”，否则会出现连接失败。

---

## 项目结构

```text
PythonProject/
├─ .env                          # 本地配置（不要提交）
├─ .streamlit/config.toml        # 网页主题配置
├─ smart_voyage_requirements.txt # 依赖清单
├─ README.md
└─ SmartVoyage/
   ├─ app.py                     # Streamlit 网页客户端
   ├─ main.py                    # 命令行客户端
   ├─ config.py                  # 环境变量与配置
   ├─ main_prompts.py            # 意图识别 / 总结 / 景点推荐 Prompt
   ├─ create_logger.py           # 日志
   ├─ a2a_server/
   │  ├─ weather_server.py       # 天气 Agent :5005
   │  ├─ ticket_server.py        # 票务查询 Agent :5006
   │  └─ order_server.py         # 票务预定 Agent :5007
   ├─ mcp_server/
   │  ├─ mcp_ticket_server.py    # 票务查询工具 :8001
   │  ├─ mcp_weather_server.py   # 天气查询工具 :8002
   │  └─ mcp_order_server.py     # 票务预定工具 :8003
   ├─ sql/
   │  ├─ create_table.sql        # 建库建表（会 DROP 同名库）
   │  └─ insert_data.sql         # 示例数据 + 日期平移
   ├─ ui/theme.py                # 网页主题与响应式样式
   ├─ utils/
   │  ├─ spider_weather.py       # 天气数据抓取与定时更新
   │  └─ format.py               # 日期 / Decimal 序列化
   └─ test/                      # MCP、A2A、爬虫联调脚本
```

---

## 常见问题

**1. `Can't connect to MySQL server on 'localhost:3306'`**

配置默认端口是 `3307`，但某个脚本仍按 `3306` 连接时会报此错。检查：

- `.env` 中的 `DB_PORT` 是否与 MySQL 实际端口一致；
- 天气更新脚本 `spider_weather.py` 的连接参数是否补上了端口；
- MySQL 服务是否已启动。

**2. `处理失败：'content'` 或代理调用失败**

通常是 A2A 服务没有启动，客户端连接被拒绝。按顺序确认 5005 / 5006 / 5007 三个端口都在监听，再重试。

**3. 查询结果为空或提示 `no_data`**

先手动执行一条 SQL 验证数据：

```sql
SELECT * FROM travel_rag.train_tickets
WHERE departure_city = '北京' AND arrival_city = '上海'
LIMIT 5;
```

再确认用户问题中的城市、日期、座位类型与数据一致。示例数据日期已平移到当前日期附近，过久或过远的日期可能查不到。

**4. 网页右侧显示“离线”**

说明客户端探测不到对应 A2A 端口。启动对应 Agent 后刷新页面；若仍离线，检查端口是否被占用或被其他进程占用。

**5. 修改了端口但调用失败**

服务端监听端口和客户端 `agent_urls` 必须同时修改；MCP 端口还需同步修改对应 A2A Server 中的 `streamablehttp_client` 地址。

---

## 贡献方式

1. Fork 本仓库并从 `master` 拉出功能分支：
   ```bash
   git checkout -b feature/your-feature
   ```
2. 修改后先本地跑通受影响的 MCP / A2A 联调脚本：
   ```bash
   python -m SmartVoyage.test.test_weather_mcp_server
   python -m SmartVoyage.test.test_ticket_agent_server
   ```
3. 提交前确认没有把 `.env`、日志、密钥、本地数据库文件加入版本控制。
4. 提交并推送：
   ```bash
   git add .
   git commit -m "feat: 简要说明改动"
   git push origin feature/your-feature
   ```
5. 发起 Pull Request，说明改动内容、影响的端口 / 表结构以及验证方式。

---

## 许可证

本项目仅用于学习、课程实训与技术演示，未声明标准开源许可证。如需对外开源，请补充 `LICENSE` 文件并明确授权范围。

---

Powered by toast508 · 基于 Agent2Agent 的旅行助手系统 v2.0
