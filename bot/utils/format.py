import re


def escape_md(text: str) -> str:
    """Escape ký tự đặc biệt cho MarkdownV2"""
    if not text:
        return ""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!\\])', r'\\\1', str(text))


def md_link(text: str, url: str) -> str:
    """Tạo link clickable trong MarkdownV2"""
    return f"[{escape_md(text)}]({url})"


def format_field(emoji: str, label: str, value: str, note: str = "") -> str:
    """Format 1 dòng thông tin: emoji Label: Value (note)"""
    note_text = f" {escape_md(note)}" if note else ""
    return f"{emoji} {escape_md(label)}: {escape_md(value)}{note_text}"
