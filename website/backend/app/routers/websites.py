from fastapi import APIRouter, Query, HTTPException, status
from typing import Dict, Any, List

from app.database import db_engine
from app.models.website import ScamWebsiteCreate, ScamWebsiteResponse, ScamWebsiteCheckResponse
from app.utils.helpers import extract_domain

router = APIRouter()

@router.get("", response_model=Dict[str, List[str]], summary="Lấy danh sách tên miền lừa đảo (cho Chrome Extension)")
def get_scam_domains():
    """
    Trả về danh sách tên miền lừa đảo dưới dạng:
    
        { "domains": ["ludao.vn", "scam-demo.com", ...] }
        
    API này tương thích trực tiếp với cấu hình ApiSync của Chrome Extension.
    """
    domains = db_engine.get_scam_domains()
    return {"domains": domains}

@router.get("/list", response_model=List[ScamWebsiteResponse], summary="Lấy danh sách chi tiết các website lừa đảo")
def get_scam_websites_detail():
    """
    Trả về danh sách đầy đủ thông tin chi tiết các website lừa đảo đã duyệt.
    """
    return db_engine.get_all_scam_websites()

@router.get("/check", response_model=ScamWebsiteCheckResponse, summary="Kiểm tra một URL hoặc domain")
def check_url(url: str = Query(..., description="URL hoặc tên miền cần kiểm tra, ví dụ: https://ludao.vn/login.php")):
    """
    Trích xuất tên miền từ URL và kiểm tra độ độc hại.
    """
    domain = extract_domain(url)
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="URL hoặc tên miền truyền vào không hợp lệ"
        )
        
    result = db_engine.check_website(domain)
    
    if result:
        return ScamWebsiteCheckResponse(
            is_scam=True,
            domain=result["domain"],
            category=result.get("category", "scam"),
            description=result.get("description", "Phát hiện website lừa đảo/độc hại."),
            threat_level=result.get("threat_level", "high"),
            status=result.get("status", "approved"),
            message=f"CẢNH BÁO: Tên miền '{domain}' nằm trong danh sách ĐỘC HẠI!"
        )
    else:
        return ScamWebsiteCheckResponse(
            is_scam=False,
            domain=domain,
            message=f"Tên miền '{domain}' hiện tại chưa được báo cáo độc hại (AN TOÀN)."
        )

@router.post("", response_model=ScamWebsiteResponse, status_code=status.HTTP_201_CREATED, summary="Báo cáo/Thêm một website độc hại mới")
def add_scam_website(website: ScamWebsiteCreate):
    """
    Thêm tên miền độc hại mới vào cơ sở dữ liệu.
    """
    try:
        res = db_engine.add_website(website.model_dump())
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi hệ thống: {e}")
