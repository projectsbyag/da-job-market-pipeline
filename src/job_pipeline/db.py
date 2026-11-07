import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, Text, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/jobs.db")

# Render gives 'postgres://' — SQLAlchemy 2.x requires 'postgresql://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["connect_args"] = {"sslmode": "require"}
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **engine_kwargs)
Base = declarative_base()
Session = sessionmaker(bind=engine)


class JobPosting(Base):
    __tablename__ = "job_postings"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    company = Column(String)
    location = Column(String)
    date_posted = Column(Date)
    url = Column(String, unique=True)
    category = Column(String(80))
    description = Column(Text)
    has_sql = Column(Boolean, default=False)
    has_python = Column(Boolean, default=False)
    has_tableau = Column(Boolean, default=False)
    has_powerbi = Column(Boolean, default=False)


def init_db():
    Base.metadata.create_all(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("job_postings")}
    if "category" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE job_postings ADD COLUMN category VARCHAR(80)"))


if __name__ == "__main__":
    init_db()
    print("Database initialized.")