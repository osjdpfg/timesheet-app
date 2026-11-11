from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from ..config import DB_PATH

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Session = sessionmaker(bind=engine)


def init_db():
    from . import models  # noqa: F401
    models.Base.metadata.create_all(engine)
    
    # Автоматически добавляем новую колонку в старую базу данных, если её нет
    with engine.connect() as conn:
        try:
            res = conn.execute(text("PRAGMA table_info(documents)"))
            cols = [row[1] for row in res]
            if "instance_number" not in cols:
                conn.execute(text("ALTER TABLE documents ADD COLUMN instance_number INTEGER DEFAULT 0"))
                conn.commit()
        except Exception:
            pass


def get_session():
    return Session()
