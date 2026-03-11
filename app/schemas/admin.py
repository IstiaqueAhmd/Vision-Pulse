from pydantic import BaseModel
from typing import List

class TimeSeriesData(BaseModel):
    date: str
    count: float

class PlanDistributionData(BaseModel):
    plan_name: str
    user_count: int

class AdminOverviewResponse(BaseModel):
    total_users: int
    active_users: int
    total_videos_generated: int
    credits_consumed: int
    total_revenue: float
    refunds_issued: int
    credits_used_over_time: List[TimeSeriesData]
    videos_generated_over_time: List[TimeSeriesData]
    plan_distribution: List[PlanDistributionData]
