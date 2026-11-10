from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..config import DB_PATH

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Session = sessionmaker(bind=engine)


def init_db():
    from . import models  # noqa: F401
    models.Base.metadata.create_all(engine)


def get_session():
    return Session()