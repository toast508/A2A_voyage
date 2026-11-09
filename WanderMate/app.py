import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import asyncio
import html
import uuid
import urllib.error
import urllib.request
import streamlit as st
from python_a2a import AgentNetwork, Message, TextContent, MessageRole, Task
from langchain_openai import ChatOpenAI
import json
from datetime import datetime
import pytz
import re  # 用于清理响应

from WanderMate.config import Config
from WanderMate.create_logger import logger
from WanderMate.main_prompts import WanderMatePrompts
from WanderMate.ui.theme import inject_theme

conf = Config()

# 设置页面配置
st.set_page_config(page_title="基于A2A的WanderMate旅行助手系统", layout="wide", page_icon="🤖")

# 注入统一主题（颜色、字体、圆角、阴影、响应式规则）
inject_theme()

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent_network" not in st.session_state:
    # 存储代理URL信息，便于查看
    st.session_state.agent_urls = {
        "WeatherQueryAssistant": "http://localhost:5005",
        "TicketQueryAssistant": "http://localhost:5006",
        "TicketOrderAssistant": "http://localhost:5007"
    }
    # 初始化网络
    network = AgentNetwork(name="Travel Assistant Network")
    network.add("WeatherQueryAssistant", "http://localhost:5005")
    network.add("TicketQueryAssistant", "http://localhost:5006")
    network.add("TicketOrderAssistant", "http://localhost:5007")
    st.session_state.agent_network = network
    # 加载配置并创建LLM
    st.session_state.llm = ChatOpenAI(
        model=conf.model_name,
        api_key=conf.api_key,
        base_url=conf.base_url,
        temperature=0.1
    )
    # 存储对话历史用于意图识别
    st.session_state.conversation_history = ""

# 意图识别agent
def intent_agent(user_input):
    # 创建意图识别链：提示模板 + LLM
    chain = WanderMatePrompts.intent_prompt() | st.session_state.llm

    # 调用LLM进行意图识别
    current_date = datetime.now(pytz.timezone('Asia/Shanghai')).strftime('%Y-%m-%d')  # 获取当前日期（Asia/Shanghai时区）
    intent_response = chain.invoke(
        {"conversation_history": '\n'.join(st.session_state.conversation_history.split("\n")[-6:]), "query": user_input,
         "current_date": current_date}).content.strip()
    logger.info(f"意图识别原始响应: {intent_response}")

    # 清理响应：移除可能的Markdown代码块标记
    intent_response = re.sub(r'^```json\s*|\s*```$', '', intent_response).strip()
    logger.info(f"清理后响应: {intent_response}")
    intent_output = json.loads(intent_response)
    # 提取意图、改写问题和追问消息
    intents = intent_output.get("intents", [])
    user_queries = intent_output.get("user_queries", {})
    follow_up_message = intent_output.get("follow_up_message", "")
    logger.info(f"intents: {intents}||user_queries: {user_queries}||follow_up_message: {follow_up_message} ")

    return intents, user_queries, follow_up_message


def extract_task_message(task):
    """从任务状态中提取可读文本，兼容 {"error": ...} 与 {"content": {"text": ...}} 两种结构"""
    status_message = getattr(task.status, "message", None)
    if isinstance(status_message, dict):
        content = status_message.get("content")
        if isinstance(content, dict) and content.get("text"):
            return content["text"]
        if status_message.get("error"):
            return f"代理调用失败：{status_message['error']}"
        return json.dumps(status_message, ensure_ascii=False)
    if status_message:
        return str(status_message)
    state = getattr(task.status.state, "value", task.status.state)
    return f"代理返回异常状态：{state}"


def is_agent_online(url, timeout=1.0):
    """探测代理端口是否可连接；只要有 HTTP 响应（包括 4xx/5xx）就认为服务在线"""
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


# 主界面布局
st.markdown(
    """
    <header class="wm-header">
      <div class="wm-brand">
        <div class="wm-logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
               stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="9"></circle>
            <path d="M15.6 8.4l-2.3 5.3-5.3 2.3 2.3-5.3z"></path>
          </svg>
        </div>
        <div class="wm-brand-text">
          <div class="wm-eyebrow">A2A · Multi-Agent Travel</div>
          <h1 class="wm-title">WanderMate</h1>
          <p class="wm-subtitle">旅行智能助手 · 天气、票务、预订一站式查询</p>
        </div>
      </div>
      <div class="wm-header-meta">
        <span class="wm-pill"><span class="wm-pill-dot"></span>A2A · 多智能体</span>
      </div>
    </header>
    """,
    unsafe_allow_html=True,
)

# 两栏布局：左侧对话，右侧 Agent Card
col1, col2 = st.columns([2.15, 1], gap="large")

# 左侧对话区域
with col1:
    # 零高度标记：供窄屏媒体查询识别“最外层两栏”
    st.markdown('<div class="wm-layout-marker" aria-hidden="true"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="wm-section-head">
          <span class="wm-section-kicker">Conversation</span>
          <h2 class="wm-section-title">对话</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 空状态：只在没有历史消息时显示
    if not st.session_state.messages:
        st.markdown(
            """
            <div class="wm-empty">
              <div class="wm-empty-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
                     stroke-linecap="round" stroke-linejoin="round">
                  <path d="M4 7h16"></path>
                  <path d="M4 12h10"></path>
                  <path d="M4 17h7"></path>
                  <circle cx="18" cy="16" r="3"></circle>
                </svg>
              </div>
              <h2>今天想去哪里？</h2>
              <p>问天气、查车票，或让助手推荐景点。也可以一次问多个意图，例如“查广州到深圳的车次和天气”。</p>
              <div class="wm-suggestions">
                <span>明天上海天气怎么样？</span>
                <span>查询明天从上海到北京的机票</span>
                <span>帮我推荐北京 3 个必去景点</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 对话历史
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 输入框
    if prompt := st.chat_input("请输入您的问题..."):
        # 显示用户消息
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.conversation_history += f"\nUser: {prompt}"

        # 获取 LLM 和当前日期
        llm = st.session_state.llm
        current_date = datetime.now(pytz.timezone('Asia/Shanghai')).strftime('%Y-%m-%d')

        # 意图识别
        with st.spinner("正在为你查询…"):
            try:
                # 意图识别过程
                intents, user_queries, follow_up_message = intent_agent(prompt)

                # 根据意图输出生成响应
                if "out_of_scope" in intents:
                    # 如果意图超出范围，返回大模型直接回复
                    response = follow_up_message
                    st.session_state.conversation_history += f"\nAssistant: {response}"
                elif follow_up_message != "":
                    # 如果有追问消息，则直接返回
                    response = follow_up_message
                    st.session_state.conversation_history += f"\nAssistant: {response}"  # 更新历史
                else:  # 处理有效意图
                    responses = []  # 存储每个意图的响应列表
                    routed_agents = []  # 记录路由到的代理列表
                    for intent in intents:
                        logger.info(f"处理意图：{intent}")
                        # 根据意图确定代理名称
                        if intent == "weather":
                            agent_name = "WeatherQueryAssistant"
                        elif intent in ["flight", "train", "concert"]:
                            agent_name = "TicketQueryAssistant"
                        elif intent == "order":
                            agent_name = "TicketOrderAssistant"
                        else:
                            agent_name = None

                        # 不同意图处理方式
                        if intent == "attraction":
                            # 对于景点推荐，直接使用LLM生成
                            chain = WanderMatePrompts.attraction_prompt() | llm
                            rec_response = chain.invoke({"query": prompt}).content.strip()
                            responses.append(rec_response)
                        elif agent_name:
                            # 对于代理意图，则调用代理
                            # 1）获取问题
                            query_str = user_queries.get(intent, {})
                            logger.info(f"{agent_name} 查询：{query_str}")
                            # 2）获取代理实例
                            agent = st.session_state.agent_network.get_agent(agent_name)
                            # 3）构建历史对话信息+新查询，然后调用代理
                            chat_history = '\n'.join(st.session_state.conversation_history.split("\n")[-7:-1]) + f'\nUser: {query_str}'
                            message = Message(content=TextContent(text=chat_history), role=MessageRole.USER)
                            task = Task(id="task-" + str(uuid.uuid4()), message=message.to_dict())
                            raw_response = asyncio.run(agent.send_task_async(task))
                            logger.info(f"{agent_name} 原始响应: {raw_response}")  # 记录原始响应日志
                            # 4）处理结果
                            if raw_response.status.state == 'completed':  # 正常结果
                                agent_result = raw_response.artifacts[0]['parts'][0]['text']
                            else:  # 失败或需要补充信息：直接返回原因，不再交给总结模型
                                responses.append(extract_task_message(raw_response))
                                continue

                            # 根据代理类型总结响应
                            if agent_name == "WeatherQueryAssistant":
                                chain = WanderMatePrompts.summarize_weather_prompt() | llm
                                final_response = chain.invoke(
                                    {"query": query_str, "raw_response": agent_result}).content.strip()
                            elif agent_name == "TicketQueryAssistant":
                                chain = WanderMatePrompts.summarize_ticket_prompt() | llm
                                final_response = chain.invoke(
                                    {"query": query_str, "raw_response": agent_result}).content.strip()
                            else:
                                final_response = agent_result

                            # 5）添加到历史
                            responses.append(final_response)  # 添加到响应列表
                            routed_agents.append(agent_name)  # 记录路由代理
                        else:
                            # 不支持的意图
                            responses.append("暂不支持此意图。")

                    response = "\n\n".join(responses)
                    if routed_agents:
                        logger.info(f"路由到代理：{routed_agents}")
                    st.session_state.conversation_history += f"\nAssistant: {response}"

                # 显示助手消息
                with st.chat_message("assistant"):
                    st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
            except json.JSONDecodeError as json_err:
                logger.error(f"意图识别JSON解析失败")
                error_message = f"意图识别JSON解析失败：{str(json_err)}。请重试。"
                with st.chat_message("assistant"):
                    st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})
            except Exception as e:
                logger.error(f"处理异常: {str(e)}")
                error_message = f"处理失败：{str(e)}。请重试。"
                with st.chat_message("assistant"):
                    st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})

# 右侧 Agent 卡片区域
with col2:
    st.markdown(
        """
        <div class="wm-section-head">
          <span class="wm-section-kicker">Agent Network</span>
          <h2 class="wm-section-title">智能体</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 一次性探测所有代理状态，供状态概览与卡片复用（沿用原有健康检查逻辑）
    agent_urls = st.session_state.get("agent_urls", {})
    agent_status = {name: is_agent_online(url) for name, url in agent_urls.items()}

    display_names = {
        "WeatherQueryAssistant": "天气",
        "TicketQueryAssistant": "票务",
        "TicketOrderAssistant": "预订",
    }
    status_parts = []
    for name, _url in agent_urls.items():
        online = agent_status.get(name, False)
        label = html.escape(display_names.get(name, name))
        state_text = "在线" if online else "离线"
        state_class = "is-online" if online else "is-offline"
        status_parts.append(
            f'<span class="wm-status {state_class}"><span class="wm-status-dot"></span>'
            f'{label} · {state_text}</span>'
        )
    st.markdown(
        f'<div class="wm-status-row">{"".join(status_parts)}</div>',
        unsafe_allow_html=True,
    )

    for agent_name in st.session_state.agent_network.agents.keys():
        agent_card = st.session_state.agent_network.get_agent_card(agent_name)
        agent_url = agent_urls.get(agent_name, "未知地址")
        online = (
            agent_status[agent_name]
            if agent_name in agent_status
            else is_agent_online(agent_url)
        )

        description = getattr(agent_card, "description", "") or ""
        if description == "Agent card not available":
            description = "无法读取 Agent Card，请确认该服务是否已启动。"

        version = getattr(agent_card, "version", None) or ""
        version_text = "" if version in ("", "unknown") else f"v{version}"

        skill_parts = []
        for skill in getattr(agent_card, "skills", None) or []:
            if isinstance(skill, dict):
                skill_name = skill.get("name", "")
                skill_desc = skill.get("description", "")
            else:
                skill_name = getattr(skill, "name", "")
                skill_desc = getattr(skill, "description", "")
            skill_name = html.escape(str(skill_name or "未命名技能"))
            skill_desc_html = (
                f"<span>{html.escape(str(skill_desc))}</span>" if skill_desc else ""
            )
            skill_parts.append(
                f'<span class="wm-skill"><strong>{skill_name}</strong>{skill_desc_html}</span>'
            )
        skills_block = "".join(skill_parts) or '<span class="wm-skill is-muted">暂无技能信息</span>'

        state_text = "在线" if online else "离线"
        state_class = "is-online" if online else "is-offline"
        meta_version = (
            f'<span class="wm-agent-version">{html.escape(version_text)}</span>'
            if version_text else ""
        )

        agent_html = f"""
        <div class="wm-agent">
          <div class="wm-agent-meta">
            <span class="wm-status {state_class}"><span class="wm-status-dot"></span>{state_text}</span>
            {meta_version}
          </div>
          <p class="wm-agent-desc">{html.escape(str(description))}</p>
          <div class="wm-agent-label">技能</div>
          <div class="wm-skill-list">{skills_block}</div>
        </div>
        """
        with st.expander(agent_name, expanded=False):
            st.markdown(agent_html, unsafe_allow_html=True)
            st.markdown('<div class="wm-agent-label">地址</div>', unsafe_allow_html=True)
            st.code(agent_url, language=None)

# 页脚
st.markdown(
    '<div class="wm-footer">Powered by toast508 · 基于 Agent2Agent 的旅行助手系统 v2.0</div>',
    unsafe_allow_html=True,
)