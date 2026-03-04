from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import models here so Alembic can discover them
from app.models.music import Music
# Other models should be imported here too, e.g. User, Video
# I'll add them if they were previously somehow imported or maybe they use base.py directly.
# Wait, let me check base.py again, maybe it doesn't need to import them all, but it's good practice for migrations.
# Actually, the implementation plan said to import the new Music model.
