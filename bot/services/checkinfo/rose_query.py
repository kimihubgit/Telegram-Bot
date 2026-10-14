"""
Rose Bot Query — Service cho /checkinfo
Gửi lệnh /info đến Rose Bot (@MissRose_bot) qua Telethon,
lấy response và trích xuất thành dict trả về.
"""

import re
import asyncio
from bot.connection import get_client, is_connected
from telethon.tl.types import MessageEntityMentionName


async def query_rose_bot(chat_id: int, query: str, timeout: int = 15) -> dict | None:
    """
    Gửi /info đến Rose Bot qua Telethon, chờ response,
    parse thành dict rồi trả về luôn.
    Trả về None nếu không nhận được phản hồi.
    """
    if not is_connected():
        print("❌ Lỗi: Chưa kết nối Telegram Client!")
        return None

    client = get_client()

    try:
        command = f"/info {query}"
        sent_msg = await client.send_message(chat_id, command)
        sent_time = sent_msg.date

        response_text = None
        total_waited = 0

        while total_waited < timeout:
            await asyncio.sleep(3)
            total_waited += 3

            messages = await client.get_messages(chat_id, limit=5)

            for msg in messages:
                if msg.date < sent_time:
                    break
                if msg.id == sent_msg.id:
                    continue

                is_bot = msg.sender and getattr(msg.sender, 'bot', False)
                if is_bot and msg.text:
                    response_text = msg.text
                    break

            if response_text:
                break

        if not response_text:
            return None

        # Parse response thành dict
        return _parse_response(response_text)

    except Exception as e:
        print(f"⚠️ query_rose_bot failed: {e}")
        return None


def _parse_response(response_text: str) -> dict:
    """
    Parse response text từ Rose Bot.
    Trích xuất các trường dạng **Key**: Value thành dict.
    """
    data = {}
    print(response_text)

    # Regex tìm cấu trúc "**Tên Trường**: Giá trị"
    pattern = re.compile(r"\*\*(?P<key>[^*]+)\*\*:\s*(?P<val>.*)")

    for line in response_text.strip().split("\n"):
        match = pattern.match(line.strip())
        if match:
            key = match.group("key").strip().lower()
            val = match.group("val").strip()

            # Làm sạch dữ liệu sơ bộ (bỏ dấu backtick ` nếu có)
            val = val.replace("`", "")
            data[key] = val

    return data