#!/bin/bash

# 本地运行脚本（不使用 Docker）
# 使用方式: ./run_local.sh

# 获取脚本所在目录（即 local_operation_set 文件夹）
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=== 配置本地运行环境 ==="

# 检查依赖
echo "检查 Python 依赖..."
if ! python3 -c "import django, rest_framework, pandas" 2>/dev/null; then
    echo "安装后端依赖..."
    cd "$PROJECT_ROOT/backend"
    pip3 install -r requirements.txt
    cd "$PROJECT_ROOT"
fi

echo "检查 Node 依赖..."
if [ ! -d "$PROJECT_ROOT/my-app/node_modules" ]; then
    echo "安装前端依赖..."
    cd "$PROJECT_ROOT/my-app"
    npm install
    cd "$PROJECT_ROOT"
fi

# 备份原文件
if [ ! -f my-app/src/data/data.js.bak ]; then
    cp my-app/src/data/data.js my-app/src/data/data.js.bak
fi

# 修改前端 API 地址为本地
sed -i '' "s|http://104.154.116.63:8000|http://localhost:8000|g" my-app/src/data/data.js

echo "✓ 前端 API 已配置为 localhost:8000"

# 杀掉可能存在的旧进程
pkill -f "manage.py runserver" 2>/dev/null
pkill -f "react-scripts start" 2>/dev/null
pkill -f "node.*react" 2>/dev/null
sleep 1

# 启动后端（使用本地配置）
echo ""
echo "=== 启动后端 (Django) ==="
cd "$PROJECT_ROOT/backend"
python3 manage.py runserver 8000 --settings=mysite.settings_local > /tmp/django.log 2>&1 &
DJANGO_PID=$!
echo "Django PID: $DJANGO_PID"

# 等待后端启动
echo "等待后端启动..."
for i in {1..10}; do
    if curl -s http://localhost:8000/api/fruit-data/ > /dev/null 2>&1; then
        echo "✓ 后端已启动"
        break
    fi
    sleep 1
done

# 检查后端是否启动成功
if ! curl -s http://localhost:8000/api/fruit-data/ > /dev/null 2>&1; then
    echo "✗ 后端启动失败，查看日志:"
    cat /tmp/django.log
    
    # 恢复原文件
    if [ -f "$PROJECT_ROOT/my-app/src/data/data.js.bak" ]; then
        mv "$PROJECT_ROOT/my-app/src/data/data.js.bak" "$PROJECT_ROOT/my-app/src/data/data.js"
    fi
    exit 1
fi

# 测试API
echo "测试 API..."
curl -s http://localhost:8000/api/fruit-data/ | head -c 200
echo ""

# 启动前端
echo ""
echo "=== 启动前端 (React) ==="
cd "$PROJECT_ROOT/my-app"
PORT=3000 npm start > /tmp/react.log 2>&1 &
REACT_PID=$!
echo "React PID: $REACT_PID"

# 等待前端启动
echo "等待前端启动..."
sleep 5

echo ""
echo "==================================="
echo "  应用已启动！"
echo "==================================="
echo "后端 API: http://localhost:8000/api/fruit-data/"
echo "前端页面: http://localhost:3000"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 捕获 Ctrl+C
cleanup() {
    echo ""
    echo "正在停止服务..."
    kill $DJANGO_PID 2>/dev/null
    kill $REACT_PID 2>/dev/null
    pkill -f "manage.py runserver" 2>/dev/null
    pkill -f "react-scripts" 2>/dev/null
    
    # 恢复原文件
    if [ -f "$PROJECT_ROOT/my-app/src/data/data.js.bak" ]; then
        mv "$PROJECT_ROOT/my-app/src/data/data.js.bak" "$PROJECT_ROOT/my-app/src/data/data.js"
        echo "已恢复原文件"
    fi
    echo "服务已停止"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 保持脚本运行
wait
