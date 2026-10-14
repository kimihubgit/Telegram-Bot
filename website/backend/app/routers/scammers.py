from fastapi import APIRouter, Query, HTTPException, status
from typing import List, Optional

from app.database import db_engine
from app.models.scammer import ScammerCreate, ScammerResponse

router = APIRouter()

@router.get("/search", response_model=List[ScammerResponse], summary="Tìm kiếm kẻ lừa đảo theo nhiều tiêu chí")
def search_scammers(
    q: Optional[str] = Query(None, description="Từ khóa tìm kiếm (SĐT, STK Ngân hàng, Telegram Username, Facebook URL...)"),
    query: Optional[str] = Query(None, description="Từ khóa tìm kiếm (tên gọi khác của q)")
):
    """
    Tìm kiếm thông tin kẻ lừa đảo trong hệ thống.
    
    Hệ thống hỗ trợ tra cứu chéo theo:
    - Số điện thoại / Ví điện tử Momo
    - Số tài khoản ngân hàng / Tên chủ tài khoản ngân hàng
    - Telegram Username / Telegram User ID
    - Facebook Profile URL / Facebook ID / Facebook Name
    - Địa chỉ email
    - Địa chỉ Ví Crypto (BTC, USDT - TRC20, ERC20...)
    - Mã định danh lừa đảo (ví dụ: SCM-00001)
    """
    search_term = q or query
    if not search_term:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp từ khóa tìm kiếm (tham số 'q' hoặc 'query')"
        )
        
    results = db_engine.search_scammers(search_term)
    return results

@router.get("/{scammer_id}", response_model=ScammerResponse, summary="Lấy chi tiết hồ sơ lừa đảo theo ID")
def get_scammer_detail(scammer_id: str):
    """
    Lấy thông tin chi tiết của một hồ sơ lừa đảo thông qua ID (ví dụ: SCM-00001 hoặc MongoDB ObjectId).
    """
    result = db_engine.get_scammer_by_id(scammer_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hồ sơ lừa đảo với ID '{scammer_id}'"
        )
    return result

@router.post("", response_model=ScammerResponse, status_code=status.HTTP_201_CREATED, summary="Báo cáo / Thêm mới hồ sơ lừa đảo")
def report_scammer(scammer: ScammerCreate):
    """
    Tạo một hồ sơ lừa đảo mới. Dữ liệu đầu vào cần tuân thủ cấu trúc chi tiết 
    (bao gồm các mảng contacts, payments, incidents).
    """
    try:
        saved_scammer = db_engine.add_scammer(scammer.model_dump())
        return saved_scammer
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lưu hồ sơ lừa đảo: {e}"
        )
