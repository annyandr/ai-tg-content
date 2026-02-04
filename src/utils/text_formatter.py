"""Utility functions for text formatting"""
import re


def markdown_to_telegram_html(text: str) -> str:
    """
    Convert simple Markdown to Telegram HTML

    Supports:
    - ***bold+italic*** → <b><i>bold+italic</i></b>
    - **bold** → <b>bold</b>
    - *italic* → <i>italic</i>
    - `code` → <code>code</code>
    - [link](url) → <a href="url">link</a>

    Args:
        text: Markdown text

    Returns:
        HTML text for Telegram
    """
    if not text:
        return text

    # Bold + Italic: ***text*** → <b><i>text</i></b> (обработать СНАЧАЛА!)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', text)

    # Bold: **text** → <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # Italic: *text* → <i>text</i> (но не затрагивать уже обработанные **)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)

    # Code: `text` → <code>text</code>
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)

    # Links: [text](url) → <a href="url">text</a>
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)

    return text


def strip_markdown(text: str) -> str:
    """
    Remove Markdown formatting, leaving only plain text

    Args:
        text: Markdown text

    Returns:
        Plain text
    """
    if not text:
        return text

    # Remove bold+italic (обработать СНАЧАЛА!)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text)

    # Remove bold
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)

    # Remove italic
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)

    # Remove code
    text = re.sub(r'`(.+?)`', r'\1', text)

    # Remove links, keep text
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)

    return text
