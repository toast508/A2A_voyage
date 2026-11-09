from datetime import datetime, timedelta
import time
import schedule

now = datetime.now()
trigger_time = (now + timedelta(seconds=20)).strftime("%H:%M:%S")

print(f"[测试日志] 当前时间: {now}")
print(f"[测试日志] 设置任务在 {trigger_time} 触发 update_weather")

# 使用 lambda 延迟执行
schedule.every().day.at(trigger_time).do(lambda: print("任务已触发!"))

# 运行 30 秒以观察任务触发
end_time = now + timedelta(seconds=60)
while datetime.now() < end_time:
    schedule.run_pending()
    print(f"[测试日志] 检查待执行任务: {datetime.now()}")
    time.sleep(1)