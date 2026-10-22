# ADR-0007：存储——SQLAlchemy + Alembic，SQLite 先行，预留 PostgreSQL

- 状态：已接受
- 日期：2026-10-22

## 背景

会话与消息历史需要持久化。候选为 SQLite / MySQL / PostgreSQL。用户期望：先走 SQLite（含初期生产），后续转 PostgreSQL。

## 决策

- **SQLAlchemy 2.0（async）+ Alembic 迁移**，存储细节不透出 ORM 之外。
- **默认 SQLite**：零依赖，clone → 配 key → `docker compose up` 即跑；初期生产也可用（客服会话写入频率低，单实例够用）。
- **预留 PostgreSQL 迁移路径**：多实例部署或 RAG（pgvector）需要时切换；为此，列类型只用跨库可移植类型，JSON 数据存 JSON 字符串列（不做 PG/MySQL 专有 JSON 查询），时间统一 UTC。
- 明确**不引入 MySQL**：无现有用户基数压力时，多支持一个库只多一条测试矩阵。

## 备选方案

- **MySQL 一等公民**：否。贴近国内部署习惯，但牺牲零依赖首跑；迁移路径打开后随时可加。
- **PostgreSQL 先行**：否。RAG 属 V2 假设性需求，不据此抬高第一版部署门槛。

## 影响

- 正面：首跑路径最短；迁移是"换连接串 + 跑 Alembic"级别的改动。
- 负面：SQLite 并发写弱——单实例约束写进文档；上量即迁 PG，迁移成本已被 ORM/迁移工具压平。
