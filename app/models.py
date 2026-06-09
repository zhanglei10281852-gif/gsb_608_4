from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class Gender(str, Enum):
    male = "男"
    female = "女"


class AffairCategory(str, Enum):
    huji = "户籍"
    shebao = "社保"
    yibao = "医保"
    dibao = "低保"
    jianfang = "建房"
    jisheng = "计生"
    other = "其他"


class AffairStatus(str, Enum):
    pending = "待受理"
    processing = "办理中"
    completed = "已办结"
    rejected = "已退回"


class AnnouncementCategory(str, Enum):
    notice = "通知"
    announcement = "公告"
    policy = "政策"
    publicity = "公示"


class ResidentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    id_card: str = Field(..., min_length=18, max_length=18)
    gender: Gender
    birth_date: str
    phone: Optional[str] = None
    address: str
    village: str
    household_head: Optional[str] = None


class ResidentUpdate(BaseModel):
    phone: Optional[str] = None
    address: Optional[str] = None
    village: Optional[str] = None
    household_head: Optional[str] = None


class AffairCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    category: AffairCategory
    applicant_id: int
    description: Optional[str] = None


class AffairProcess(BaseModel):
    status: AffairStatus
    handler: str
    result: Optional[str] = None


class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str
    category: AnnouncementCategory
    publisher: str
    is_pinned: bool = False
