# 本地运行指南（不使用 Docker）

## 文件说明

本项目包含本地运行所需的所有配置文件，位于 `local_operation_set` 文件夹中：

| 文件 | 说明 |
|------|------|
| `local_operation_set/run_local.sh` | 一键启动脚本 |
| `local_operation_set/.env.local` | React 本地环境变量 |
| `local_operation_set/settings_local.py` | 配置说明文件 |
| `local_operation_set/api_views.py` | 本地视图（修复数据路径） |
| `local_operation_set/api_urls.py` | 本地 URL 配置 |
| `backend/mysite/settings_local.py` | Django 本地配置 |
| `backend/mysite/api_views_local.py` | 本地视图副本 |
| `backend/mysite/api_urls_local.py` | 本地 URL 副本 |

---

## 方式一：使用启动脚本（推荐）

```bash
./local_operation_set/run_local.sh
```

脚本会自动：
1. 检查并安装依赖（如需要）
2. 配置前端 API 指向本地后端
3. 启动 Django 后端 (端口 8000)
4. 启动 React 前端 (端口 3000)
5. 停止时自动恢复原文件

---

## 方式二：手动运行

### 1. 启动后端

```bash
cd backend

# 安装依赖（如果还没安装）
pip3 install -r requirements.txt

# 启动服务器（使用本地配置）
python3 manage.py runserver 8000 --settings=mysite.settings_local
```

### 2. 启动前端

```bash
cd my-app

# 安装依赖（如果还没安装）
npm install

# 启动开发服务器
npm start
```

---

## 访问

- 前端页面: http://localhost:3000
- 后端 API: http://localhost:8000/api/fruit-data/

---

## 注意事项

- **停止脚本**后会自动恢复 `data.js` 原文件
- 如果脚本运行失败，可手动恢复：
  ```bash
  mv my-app/src/data/data.js.bak my-app/src/data/data.js
  ```
- 原 `data.js` 配置为远程服务器，停止本地运行后需恢复
