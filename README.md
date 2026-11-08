# SmartVoyage 旅行RAG多智能体系统
基于大模型 + RAG检索增强的多Agent旅行规划助手，支持目的地咨询、行程定制、景点查询、知识库检索。

## ✨ 项目简介
本项目采用多智能体架构，结合RAG向量检索，实现智能化旅行方案生成。
用户输入旅行需求，系统自动检索本地知识库，调用大模型生成行程、景点推荐、美食住宿建议，适合课程大作业展示。

- 多Agent分工协作
- RAG本地知识库检索，减少幻觉
- 支持自定义旅行语料库
- 对接DeepSeek大模型API
- MySQL存储相关数据

## 🧰 环境依赖
Python >= 3.11
```bash
pip install -r smart_voyage_requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
## ⚙️ 配置说明

打开 `config.py` 修改配置：

```
# 大模型
self.api_key = "你的API_KEY"
self.base_url = "模型网关地址"
self.model_name = "deepseek-chat"

# MySQL数据库
self.host = 'localhost'
self.user = 'root'
self.password = '123456'
self.database = 'travel_rag'
```

> 
> ⚠️ 重要：**不要直接把带真实密钥的 config.py 上传到公网仓库！**
> 建议复制一份 `config_example.py` 作为模板，密钥放到环境变量 /.env

## 🚀 运行步骤

1. 创建并激活虚拟环境

```
python -m venv .venv
# Windows
.venv\Scripts\activate
```

2. 安装依赖

```
pip install -r smart_voyage_requirements.txt
```

3. 初始化 MySQL，执行 sql 目录下建表语句
4. 填入大模型 API 密钥，检查数据库连通
5. 启动项目

```
python main.py
```

## 📚 知识库语料

内置默认旅行语料，支持自行新增旅游景点、攻略、美食文本，导入向量库用于 RAG 检索。

## 📝 功能示例

- 用户：帮我规划上海 3 天短途旅行
- Agent：检索景点知识库，生成行程、交通、美食、住宿方案

## 📌 注意事项

1. 本项目为课程实训项目，仅供学习演示
2. API 密钥、数据库密码禁止公开提交
3. 数据库需要提前本地启动 MySQL 服务
4. 大模型调用需要保证网络可访问网关地址

## 📄 License

仅供学习交流使用
