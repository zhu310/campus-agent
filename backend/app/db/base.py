"""所有 SQLAlchemy ORM 模型共享的声明式基类。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """用于汇总模型元数据，供启动建表和 ORM 映射使用。"""

    pass
