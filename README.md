# 餐厅点菜平台

Flask 餐厅点菜与经营管理系统，支持多餐厅、点餐、结账与智能问答（GPT）。

## 配置

1. 复制环境配置模板并编辑：

   ```bash
   cp .env.example .env
   ```

2. 在 `.env` 中填写：

   - **SECRET_KEY**：会话加密密钥，生产环境务必改为随机字符串
   - **DATABASE_URL**：数据库连接，默认 SQLite（`sqlite:///restaurant_platform.db`）
   - **GPT_BASE_URL** / **GPT_API_KEY** / **GPT_MODEL**：GPT API 地址、密钥与模型，用于智能问答；不填则问答功能不可用

## 运行

1. 创建虚拟环境并安装依赖：

   ```bash
   python -m venv venv
   venv\Scripts\activate    # Windows
   pip install -r requirements.txt
   ```

2. 确保已配置 `.env`（见上方）。

3. 启动应用：

   ```bash
   python app.py
   ```

   默认访问：<http://127.0.0.1:5001>

4. 首次运行会自动创建数据库表；如需手动初始化：

   ```bash
   flask init-db
   ```
