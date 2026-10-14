from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ScamWebsiteBase(BaseModel):
    domain: str = Field(..., description="Tên miền của trang web lừa đảo, ví dụ: scam-demo.com")
    category: str = Field("phishing", description="Loại độc hại: phishing, scam, gambling, malware, counterfeit...")
    description: Optional[str] = Field(None, description="Mô tả chi tiết về hành vi lừa đảo của website")
    threat_level: str = Field("high", description="Mức độ đe dọa: high, medium, low")
    status: str = Field("approved", description="Trạng thái duyệt: approved, pending, rejected, whitelisted")
    reported_by: Optional[str] = Field(None, description="Thông tin người báo cáo hoặc nguồn cấp tin")

class ScamWebsiteCreate(ScamWebsiteBase):
    pass

class ScamWebsiteResponse(ScamWebsiteBase):
    id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ScamWebsiteCheckResponse(BaseModel):
    is_scam: bool
    domain: str
    category: Optional[str] = None
    description: Optional[str] = None
    threat_level: Optional[str] = None
    status: Optional[str] = None
    message: str
