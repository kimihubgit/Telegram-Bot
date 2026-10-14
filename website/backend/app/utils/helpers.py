import re
from urllib.parse import urlparse

def extract_domain(url_or_domain: str) -> str:
    """
    Trích xuất tên miền chuẩn từ một URL hoặc chuỗi nhập vào.
    Ví dụ: 
      "https://www.scam-demo.com/login?token=abc" -> "scam-demo.com"
      "scam-demo.com" -> "scam-demo.com"
      "sub.domain.ludao.vn/index.html" -> "sub.domain.ludao.vn"
    """
    if not url_or_domain:
        return ""
    
    url_or_domain = url_or_domain.strip().lower()
    
    # Nếu không có protocol, thêm // để urlparse hoạt động đúng
    if not url_or_domain.startswith(("http://", "https://", "//")):
        # Nếu chuỗi chứa dấu gạch chéo (/), urlparse có thể nhận diện sai
        # Ví dụ: "ludao.vn/nap-the" -> urlparse coi "ludao.vn" là scheme nếu không cẩn thận
        # Ta tạm thời coi phần trước dấu / đầu tiên là domain
        if "/" in url_or_domain:
            url_or_domain = "http://" + url_or_domain
        else:
            url_or_domain = "//" + url_or_domain
            
    try:
        parsed = urlparse(url_or_domain)
        hostname = parsed.hostname or ""
        
        # Loại bỏ tiền tố 'www.' nếu có
        if hostname.startswith("www."):
            hostname = hostname[4:]
            
        return hostname
    except Exception:
        # Fallback xử lý thô bằng Regex nếu urlparse lỗi
        match = re.search(r'(?:https?://)?(?:www\.)?([^/:\s?#]+)', url_or_domain)
        if match:
            return match.group(1)
        return url_or_domain

def clean_phone_number(phone: str) -> str:
    """
    Chuẩn hóa số điện thoại về dạng số đơn thuần để dễ so khớp.
    Ví dụ: "+84 901-234-567" -> "84901234567"
    """
    if not phone:
        return ""
    # Chỉ giữ lại các chữ số
    cleaned = re.sub(r'\D', '', phone)
    # Nếu bắt đầu bằng 0 ở Việt Nam, có thể đổi thành 84 hoặc giữ nguyên cả hai
    return cleaned
