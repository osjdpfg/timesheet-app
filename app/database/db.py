from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from ..config import DB_PATH

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Session = sessionmaker(bind=engine)


def init_db():
    from . import models  # noqa: F401
    models.Base.metadata.create_all(engine)
    
    with engine.connect() as conn:
        try:
            res = conn.execute(text("PRAGMA table_info(documents)"))
            cols = [row[1] for row in res]
            if "instance_number" not in cols:
                conn.execute(text("ALTER TABLE documents ADD COLUMN instance_number INTEGER DEFAULT 0"))
            if "linked_schedule_id" not in cols:
                conn.execute(text("ALTER TABLE documents ADD COLUMN linked_schedule_id INTEGER REFERENCES documents(id)"))
            
            res = conn.execute(text("PRAGMA table_info(employees)"))
            cols = [row[1] for row in res]
            if "auto_7h" not in cols:
                conn.execute(text("ALTER TABLE employees ADD COLUMN auto_7h BOOLEAN DEFAULT 0"))
            
            res = conn.execute(text("PRAGMA table_info(document_rows)"))
            cols = [row[1] for row in res]
            if "auto_7h" not in cols:
                conn.execute(text("ALTER TABLE document_rows ADD COLUMN auto_7h BOOLEAN DEFAULT 0"))
                
            conn.commit()
        except Exception:
            pass


def get_session():
    return Session()
