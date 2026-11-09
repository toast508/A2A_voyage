import os

from dotenv import load_dotenv

# 项目根目录
project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

# 加载项目根目录下的 .env（已存在的环境变量优先，不会被覆盖）
load_dotenv(os.path.join(project_root, '.env'))


#定义配置文件
class Config:
    def __init__(self):
        # 大模型配置
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.model_name = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")

        # 数据库配置
        self.host = os.getenv("DB_HOST", 'localhost')
        self.user = os.getenv("DB_USER", 'root')
        self.port = int(os.getenv("DB_PORT", 3307))  
        self.password = os.getenv("DB_PASSWORD")
        self.database = os.getenv("DB_DATABASE", 'travel_rag')

        # 日志配置
        self.log_file = os.path.join(project_root, 'WanderMate', 'logs/app.log')


if __name__ == '__main__':
    print(Config().log_file)
