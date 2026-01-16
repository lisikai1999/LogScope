#!/bin/bash

# 启动脚本 - 同时运行 Python 后端和 Vue3 前端

# 进入后端目录，安装依赖并启动
cd backend
pip install -r requirements.txt -q
python main.py &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 进入前端目录，安装依赖并启动
cd ../frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5000 &
FRONTEND_PID=$!

# 保存 PID
echo $BACKEND_PID > /tmp/backend.pid
echo $FRONTEND_PID > /tmp/frontend.pid

echo "Backend started with PID: $BACKEND_PID"
echo "Frontend started with PID: $FRONTEND_PID"

# 等待进程
wait $BACKEND_PID $FRONTEND_PID
