#!/usr/bin/env python3
"""Pinterest Shop-the-Look scraper using ScrapingBee network/XHR capture."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests
from scrapingbee import ScrapingBeeClient

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

PIN_LINK_PATTERN = re.compile(
    r'href="(https://www\.pinterest\.com/pin/\d+/|/pin/\d+/)"',
    flags=re.IGNORECASE,
)
IMG_PATTERN = re.compile(
    r'<img[^>]+src="([^"]+)"',
    flags=re.IGNORECASE,
)
SHOPPING_ENDPOINT = "https://www.pinterest.com/resource/ApiResource/get/"


def load_scrapingbee_key(env_path: Path) -> str:
    key = os.getenv("SCRAPINGBEE_API_KEY")
    if key:
        return key

    if not env_path.exists():
        raise RuntimeError(f".env file not found at {env_path}")

    for line in env_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        var, value = text.split("=", 1)
        if var.strip() == "SCRAPINGBEE_API_KEY":
            clean = value.strip().strip('"').strip("'")
            if clean:
                return clean
    raise RuntimeError("SCRAPINGBEE_API_KEY is missing in environment or .env")


def build_search_url(keyword: str) -> str:
    query = f"{keyword} clothing product catalog"
    return f"https://www.pinterest.com/search/pins/?q={quote_plus(query)}"


def extract_top_pin_urls(html: str, limit: int = 5) -> list[str]:
    seen: set[str] = set()
    pins: list[str] = []
    for match in PIN_LINK_PATTERN.finditer(html):
        href = match.group(1)
        full = href if href.startswith("http") else f"https://www.pinterest.com{href}"
        if full in seen:
            continue
        seen.add(full)
        pins.append(full)
        if len(pins) >= limit:
            break
    return pins


def extract_candidate_images(html: str) -> list[str]:
    candidates: list[str] = []
    for match in IMG_PATTERN.finditer(html):
        src = match.group(1)
        if "i.pinimg.com" in src:
            candidates.append(src.replace("&amp;", "&"))
    return candidates


def to_originals_url(url: str) -> str:
    out = re.sub(r"/(236x|474x)/", "/originals/", url)
    if out == url:
        out = re.sub(r"/(564x|736x)/", "/originals/", url)
    return out


def to_736_url(url: str) -> str:
    return re.sub(r"/originals/", "/736x/", url)


def url_exists(url: str) -> bool:
    try:
        response = requests.head(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=10,
            allow_redirects=True,
        )
        if response.status_code == 404:
            return False
        return 200 <= response.status_code < 400
    except requests.RequestException:
        return False


def choose_high_res_image(url: str | None) -> str | None:
    if not url:
        return None
    original = to_originals_url(url)
    if original != url and url_exists(original):
        return original
    fallback = to_736_url(original if original != url else url)
    if url_exists(fallback):
        return fallback
    return original if original != url else url


def parse_json_safely(data: Any) -> Any | None:
    if data is None:
        return None
    if isinstance(data, (dict, list)):
        return data
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="ignore")
    if isinstance(data, str):
        text = data.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    return None


def get_value(d: dict[str, Any], path: list[str], default: Any = None) -> Any:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def extract_network_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for key in ("xhr_responses", "network_logs", "xhr", "requests"):
        value = payload.get(key)
        if isinstance(value, list):
            entries.extend([entry for entry in value if isinstance(entry, dict)])
    return entries


def normalize_entry_url(entry: dict[str, Any]) -> str:
    return (
        str(entry.get("url") or "")
        or str(get_value(entry, ["request", "url"], ""))
        or str(get_value(entry, ["request_url"], ""))
    )


def normalize_entry_body(entry: dict[str, Any]) -> Any:
    return (
        entry.get("body")
        or get_value(entry, ["response", "body"])
        or entry.get("response_body")
        or get_value(entry, ["response", "text"])
        or entry.get("text")
    )


def get_first_valid_shopping_carousel(payload: dict[str, Any]) -> dict[str, Any] | None:
    for entry in extract_network_entries(payload):
        request_url = normalize_entry_url(entry)
        if SHOPPING_ENDPOINT not in request_url:
            continue

        body_obj = parse_json_safely(normalize_entry_body(entry))
        if not isinstance(body_obj, dict):
            continue

        resource_response = body_obj.get("resource_response")
        if not isinstance(resource_response, dict):
            continue

        endpoint_name = str(resource_response.get("endpoint_name", ""))
        if "shopping_carousel" not in endpoint_name:
            continue

        data = resource_response.get("data")
        if not isinstance(data, list) or not data:
            # Decoy result, continue scanning.
            continue

        return body_obj
    return None


def pick_cutout_url(images: Any) -> str | None:
    if not isinstance(images, dict):
        return None
    priority_keys = ("orig", "originals", "736x", "564x", "474x")
    for key in priority_keys:
        value = images.get(key)
        if isinstance(value, dict) and value.get("url"):
            return str(value["url"])
        if isinstance(value, str):
            return value
    for value in images.values():
        if isinstance(value, dict) and value.get("url"):
            return str(value["url"])
    return None


def pick_coordinates(item: dict[str, Any]) -> tuple[Any, Any]:
    if "x" in item or "y" in item:
        return item.get("x"), item.get("y")
    for key in ("position", "coords", "bbox"):
        val = item.get(key)
        if isinstance(val, dict) and ("x" in val or "y" in val):
            return val.get("x"), val.get("y")
    return None, None


def is_clothing_item(item: dict[str, Any]) -> bool:
    type_fields = [
        item.get("type"),
        item.get("item_type"),
        item.get("entity_type"),
        get_value(item, ["rich_summary", "type"]),
        get_value(item, ["rich_summary", "category"]),
    ]
    known = [str(v).lower() for v in type_fields if v]
    if not known:
        return True
    return any("clothing" in value or "apparel" in value for value in known)


def extract_shop_items(shopping_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rr = shopping_payload.get("resource_response", {})
    data = rr.get("data", [])
    if not isinstance(data, list):
        return []

    items: list[dict[str, Any]] = []
    for object in data:
        if not isinstance(object, dict):
            continue
        # if not is_clothing_item(item):
        #     continue
        
        nodes = object.get("objects")
        
        for item in nodes:

            images = item.get("images")
            cutout = pick_cutout_url(images)
            outbound = (
                item.get("outbound_url")
                or item.get("link")
                or item.get("destination_url")
                or get_value(item, ["rich_summary", "url"])
            )
            title = item.get("title", "")
            
            description = (
                item.get("description")
                or item.get("name")
                or get_value(item, ["rich_summary", "display_description"])
                or get_value(item, ["rich_summary", "title"])
                or ""
            )
            
            x, y = pick_coordinates(item)
            items.append(
                {
                    "type": item.get("type") or item.get("item_type") or item.get("entity_type"),
                    "cutout_url": cutout,
                    "store_link": outbound,
                    "title": title,
                    "description": description,
                    "x": x,
                    "y": y,
                }
            )
    return items


def scrape_keyword(keyword: str, api_key: str) -> list[dict[str, Any]]:
    client = ScrapingBeeClient(api_key=api_key)

    search_url = build_search_url(keyword)
    search_resp = client.get(
        search_url,
        params={"render_js": "true", "wait": "2500"},
        headers={"User-Agent": USER_AGENT},
    )
    html = search_resp.content.decode("utf-8", errors="ignore")

    pin_urls = extract_top_pin_urls(html, limit=5) ## FIXEME
    image_candidates = extract_candidate_images(html)

    results: list[dict[str, Any]] = []
    for idx, pin_url in enumerate(pin_urls):
        
        main_image = image_candidates[idx] if idx < len(image_candidates) else None
        high_res_main_image = choose_high_res_image(main_image)

        
        
        error_message = None 
        
        pin_resp = client.get(
                pin_url,
                params={"render_js": "true", "json_response": "true", "wait": "3000"},
                headers={"User-Agent": USER_AGENT},
            )
        pin_payload = parse_json_safely(pin_resp.content)
        
        if not isinstance(pin_payload, dict):
            raise ValueError("Pin response JSON was not an object")

        shopping_payload = get_first_valid_shopping_carousel(pin_payload)
        shop_items = extract_shop_items(shopping_payload) if shopping_payload else []
        
        # try:
            
        # except Exception as exc:  # noqa: BLE001
        #     shop_items = []
        #     error_message = str(exc)
        # else:
        #     error_message = None

        pin_result = {
            "pin_url": pin_url,
            "main_pin_image_high_res": high_res_main_image,
            "shop_the_look_items": shop_items,
        }
        
        # print(pin_result)
        # raise
        if error_message:
            pin_result["error"] = error_message
        results.append(pin_result)
    return results


def parse_args() -> argparse.Namespace:
    default_env = str(Path(__file__).with_name(".env"))
    parser = argparse.ArgumentParser(
        description="Scrape Pinterest Shop-the-Look cutouts from XHR JSON via ScrapingBee."
    )
    parser.add_argument("keyword", help='Input keyword, e.g. "Neo-Deco"')
    parser.add_argument(
        "--env-file",
        default=default_env,
        help="Path to environment file containing SCRAPINGBEE_API_KEY (default: .env)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env_path = Path(args.env_file)
    try:
        api_key = load_scrapingbee_key(env_path)
        output = scrape_keyword(args.keyword, api_key)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.pretty:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
