from app.db.base_class import Base

# Import models here so Alembic can discover them
from app.models.music import Music
from app.models.user import User
from app.models.video import Video
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.models.credit import CreditPackage, CreditTransaction
