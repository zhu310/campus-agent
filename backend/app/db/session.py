"""数据库引擎和按请求生命周期管理的会话依赖。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings


# 引擎放在模块级别，所有路由复用同一个连接池，避免每次请求重复创建连接。
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """向路由提供数据库会话，并在请求结束后确保关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
