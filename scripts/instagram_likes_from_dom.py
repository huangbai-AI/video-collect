"""Turn rendered Instagram likes cards into video links for store.py ingest.

Input: JSON array of {"label": card aria-label, "key": thumbnail ig_cache_key}.
Output: {"items": [...]} on stdout. Only visible Video cards are included.
"""

import argparse
import base64
import binascii
import json
import re
import sys


ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
VIDEO_LABEL = re.compile(r"^Video, \d+ of \d+, by @([^,]+), shared ")


def shortcode(media_id):
    number = int(media_id)
    if number <= 0:
        raise ValueError("invalid media ID")
    digits = []
    while number:
        number, remainder = divmod(number, 64)
        digits.append(ALPHABET[remainder])
    return "".join(reversed(digits))


def media_id_from_cache_key(key):
    first_part = key.split(".", 1)[0]
    padded = first_part + "=" * (-len(first_part) % 4)
    decoded = base64.b64decode(padded, validate=True).decode("ascii")
    if not decoded.isdecimal() or len(decoded) < 19:
        raise ValueError("invalid Instagram cache key")
    # Some thumbnail keys append the account ID after the 19-digit media ID.
    return decoded[:19]


def convert(cards):
    items = []
    seen = set()
    for card in cards:
        if not isinstance(card, dict):
            continue
        match = VIDEO_LABEL.match(card.get("label", ""))
        key = card.get("key")
        if not match or not isinstance(key, str):
            continue
        try:
            vid = shortcode(media_id_from_cache_key(key))
        except (ValueError, UnicodeDecodeError, binascii.Error):
            continue
        if vid in seen:
            continue
        seen.add(vid)
        items.append({
            "vid": vid,
            "url": f"https://www.instagram.com/p/{vid}/",
            "type": "video",
            "author": match.group(1),
        })
    return {"items": items}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON file of rendered likes cards")
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as file:
        cards = json.load(file)
    if not isinstance(cards, list):
        parser.error("input must be a JSON array")
    json.dump(convert(cards), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
