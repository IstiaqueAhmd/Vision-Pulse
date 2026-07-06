from app.db.base_class import Base

# Import models here so Alembic can discover them
from app.models.music import Music
from app.models.user import User
from app.models.video import Video
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.models.credit import CreditPackage, CreditTransaction
from app.models.logs import Logs
from app.models.payments import Payment
from app.models.faq import FAQ
from app.models.policies import Policies
from app.models.notification import Notification
from app.models.token_blocklist import TokenBlocklist