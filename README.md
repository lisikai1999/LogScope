# Docker 日志查看器

Docker 日志查看网页应用，支持时间筛选日志。

## 技术栈

### 后端
- **Python 3.11+**
- **FastAPI** - 高性能 Web 框架
- **Docker SDK for Python** - Docker API 交互

### 前端
- **Vue 3** - 渐进式 JavaScript 框架
- **Vue Router** - 路由管理
- **Vite** - 快速的前端构建工具
- **Axios** - HTTP 客户端

## 功能特性

### 容器列表页面
- 显示所有 Docker 容器
- 支持搜索容器名称、镜像或 ID
- 支持显示/隐藏已停止的容器
- 显示容器状态、镜像、创建时间等信息
- 快速跳转到日志查看器

### 日志查看器页面
- 查看容器实时日志
- **时间范围筛选** - 支持自定义开始时间和结束时间
- **快速时间选择** - 最近1小时、24小时、7天、全部
- **日志行数限制** - 可指定返回的日志行数
- **日志类型筛选** - 分别显示/隐藏标准输出(stdout)和错误输出(stderr)
- **自动刷新** - 可选开启 5 秒自动刷新
- 终端风格的日志显示，便于阅读

## 项目结构

```
.
├── backend/                 # Python 后端
│   ├── main.py             # FastAPI 主应用
│   ├── docker_service.py   # Docker 服务封装
│   └── requirements.txt    # Python 依赖
├── frontend/               # Vue3 前端
│   ├── src/
│   │   ├── App.vue        # 主组件
│   │   ├── main.js        # 入口文件
│   │   └── views/         # 页面组件
│   │       ├── ContainerList.vue  # 容器列表
│   │       └── LogViewer.vue      # 日志查看器
│   ├── index.html         # HTML 模板
│   ├── vite.config.js     # Vite 配置
│   └── package.json       # Node 依赖
├── start.sh               # 启动脚本
└── .coze                  # 项目配置
```

## API 接口

### 获取容器列表
```
GET /api/containers?all={boolean}
```

### 获取容器日志
```
GET /api/containers/{container_id}/logs?since={timestamp}&until={timestamp}&tail={number}
```

参数说明：
- `since`: 起始时间戳（Unix 时间戳，秒）
- `until`: 结束时间戳（Unix 时间戳，秒）
- `tail`: 返回最后 N 行日志

### 获取容器详情
```
GET /api/containers/{container_id}/info
```

### 启动容器
```
POST /api/containers/{container_id}/start
```

### 停止容器
```
POST /api/containers/{container_id}/stop
```

## 安装和运行

### 开发环境
使用 `coze dev` 命令启动开发环境：
```bash
coze dev
```

服务将运行在：
- 前端：http://localhost:5000
- 后端：http://localhost:8000

### 手动启动

#### 后端
```bash
cd backend
pip install -r requirements.txt
python main.py
```

#### 前端
```bash
cd frontend
npm install
npm run dev
```

## 注意事项

1. **Docker Socket 访问**：应用需要访问 Docker socket (`/var/run/docker.sock`)
2. **演示模式**：如果 Docker 不可用，应用会自动切换到演示模式，显示模拟数据
3. **端口配置**：前端默认使用 5000 端口，后端使用 8000 端口

## 时间筛选功能详解

时间筛选是本应用的核心功能，支持多种方式：

### 1. 自定义时间范围
通过日期时间选择器设置：
- **开始时间**：只显示该时间之后的日志
- **结束时间**：只显示该时间之前的日志

### 2. 快速时间选择
提供预设时间范围：
- **最近1小时**：查看最近 1 小时的日志
- **最近24小时**：查看最近 1 天的日志
- **最近7天**：查看最近 7 天的日志
- **全部**：显示所有日志

### 3. 日志行数限制
可以限制返回的日志行数，避免加载过多数据。

### 4. 日志类型筛选
- **标准输出 (stdout)**：应用程序的正常输出
- **错误输出 (stderr)**：错误和警告信息

## 许可证
