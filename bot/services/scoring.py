"""
Scoring Service
Tính toán điểm tín nhiệm tài khoản dựa trên độ hoàn thiện Profile (X),
tổng sao của Quà tặng (Y) và số lượng Quà giới hạn (Z).
"""

def calculate_scores(profile_info: dict, gift_data: dict | None, is_rose: bool = False) -> dict:
    """
    Tính toán chỉ số tín nhiệm (X, Y, Z) và phân hạng tài khoản.
    
    - X (Profile Info): Điểm hoàn thiện thông tin.
    - Y (Gift Stars): Tổng sao từ quà tặng nhận được.
    - Z (Limited Gifts): Số lượng quà tặng hiếm/giới hạn.
    
    Returns:
        dict: {
            "score_x": int,
            "score_y": int,
            "score_z": int,
            "rank_html": str,       # Định dạng HTML để hiển thị
            "rank_markdown": str    # Định dạng MarkdownV2 để hiển thị
        }
    """
    # 1. Tính chỉ số X (Profile Info)
    score_x = 0
    if is_rose:
        if profile_info.get('username'):
            score_x += 2
        if profile_info.get('first name'):
            score_x += 1
        if profile_info.get('last name'):
            score_x += 1
        if profile_info.get('user link') and "tg://user" in profile_info.get('user link'):
            score_x += 2
    else:
        if profile_info.get('username'):
            score_x += 1
        if profile_info.get('first_name'):
            score_x += 1
        if profile_info.get('id'):
            score_x += 1

    # 2. Tính chỉ số Y (Quà thường) & Z (Quà giới hạn)
    score_y = 0
    score_z = 0
    gifts_list = gift_data.get('gifts', []) if gift_data else []

    for user_gift in gifts_list:
        if isinstance(user_gift, dict):
            buy_price = user_gift.get('stars', 0) or user_gift.get('convert_stars', 0)
            is_limited = user_gift.get('limited', False) or (user_gift.get('availability_total') is not None)
        else:
            gift_obj = getattr(user_gift, 'gift', None)
            buy_price = getattr(user_gift, 'stars', 0) or (getattr(gift_obj, 'stars', 0) if gift_obj else 0)
            if not buy_price:
                buy_price = getattr(user_gift, 'convert_stars', 0) or (getattr(gift_obj, 'convert_stars', 0) if gift_obj else 0)
            is_limited = getattr(user_gift, 'limited', False) or (getattr(user_gift, 'availability_total', None) is not None)

        score_y += int(buy_price) if buy_price else 0
        if is_limited:
            score_z += 1
    return {
        "score_x": score_x,
        "score_y": score_y,
        "score_z": score_z,
        "rank_html": f"<code>{score_x}</code> | <code>{score_y:,}</code> | <code>{score_z}</code>",
        "rank_markdown": f"`{score_x}` \\| `{score_y:,}` \\| `{score_z}`"
    }
