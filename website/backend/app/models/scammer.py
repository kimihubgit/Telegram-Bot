from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- Contacts Models ---
class TelegramContact(BaseModel):
    username: Optional[str] = None
    id: Optional[Any] = None  # Có thể là int hoặc str

class FacebookContact(BaseModel):
    id: Optional[Any] = None
    link: Optional[str] = None
    name: Optional[str] = None

class PhoneContact(BaseModel):
    full_number: str
    country_code: Optional[str] = None
    national_number: Optional[str] = None
    iso_country: Optional[str] = None
    carrier: Optional[str] = None
    tag: Optional[List[str]] = Field(default_factory=list)

class EmailContact(BaseModel):
    address: str
    tag: Optional[List[str]] = Field(default_factory=list)

class ContactSection(BaseModel):
    telegram: Optional[List[TelegramContact]] = Field(default_factory=list)
    facebook: Optional[List[FacebookContact]] = Field(default_factory=list)
    phone: Optional[List[PhoneContact]] = Field(default_factory=list)
    email: Optional[List[EmailContact]] = Field(default_factory=list)
    other: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

# --- Payments Models ---
class BankPayment(BaseModel):
    bank_name: str
    short_name: str
    account_number: str
    account_holder: str
    bin_code: Optional[str] = None

class WalletPayment(BaseModel):
    platform: str  # Momo, ZaloPay, ViettelMoney...
    phone_number: str
    owner_name: Optional[str] = None

class CryptoPayment(BaseModel):
    network: str  # TRC20, ERC20...
    address: str
    coin: str  # USDT, BTC...

class BinancePayment(BaseModel):
    binance_id: str
    tag: Optional[List[str]] = Field(default_factory=list)

class PaymentSection(BaseModel):
    bank: Optional[List[BankPayment]] = Field(default_factory=list)
    wallet: Optional[List[WalletPayment]] = Field(default_factory=list)
    crypto: Optional[List[CryptoPayment]] = Field(default_factory=list)
    binance: Optional[List[BinancePayment]] = Field(default_factory=list)
    paypal: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    other: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

# --- Incidents Models ---
class LossItem(BaseModel):
    amount: float
    currency: str = "VND"

class IncidentRaw(BaseModel):
    detail: Optional[str] = None
    images: Optional[List[str]] = Field(default_factory=list)
    posts: Optional[List[str]] = Field(default_factory=list)
    other: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

class IncidentReference(BaseModel):
    report_id: Optional[str] = None
    scammer_id: Optional[str] = None

class IncidentItem(BaseModel):
    incident_id: Optional[str] = None  # Dùng trong scam-demo.json
    ref: Optional[IncidentReference] = None  # Dùng trong scammer.json
    scam_type: Optional[str] = None  # Dùng trong scam-demo.json
    type: Optional[str] = None  # Dùng trong scammer.json
    date: Optional[str] = None
    status: Optional[str] = "active"
    losses: Optional[List[LossItem]] = Field(default_factory=list)  # Dùng trong scammer.json
    total_loss: Optional[float] = 0.0  # Dùng trong scam-demo.json
    currency: Optional[str] = "VND"
    description: Optional[str] = None
    evidence: Optional[IncidentRaw] = None  # Dùng trong scam-demo.json
    raw: Optional[IncidentRaw] = None  # Dùng trong scammer.json
    reported_at: Optional[str] = None

# --- Main Scammer Models ---
class MetadataSection(BaseModel):
    created_at: str = Field(default_from_utcnow=True)
    updated_at: str = Field(default_from_utcnow=True)

class ScammerBase(BaseModel):
    contact: ContactSection = Field(default_factory=ContactSection)
    payments: PaymentSection = Field(default_factory=PaymentSection)
    incidents: Optional[List[IncidentItem]] = Field(default_factory=list)  # Dùng cho scammer.json
    incident: Optional[List[IncidentItem]] = Field(default_factory=list)   # Dùng cho scam-demo.json (tương thích cả hai)
    status: str = "approved"  # approved, pending, rejected
    scammer_id: Optional[str] = None

class ScammerCreate(ScammerBase):
    pass

class ScammerResponse(ScammerBase):
    id: Optional[str] = None  # MongoDB ObjectId string nếu có
    metadata: MetadataSection
