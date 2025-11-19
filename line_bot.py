import os
import json
from typing import Dict, List

from flask import Flask, request, abort

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ========= LINE 設定 =========
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

if not CHANNEL_SECRET or not CHANNEL_ACCESS_TOKEN:
    raise ValueError("請先在 Render 設定 LINE_CHANNEL_SECRET 和 LINE_CHANNEL_ACCESS_TOKEN")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ========= Google Sheet 設定 =========
SERVICE_ACCOUNT_JSON_STR = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

if not SERVICE_ACCOUNT_JSON_STR or not SHEET_ID:
    raise ValueError("請先在 Render 設定 GOOGLE_SERVICE_ACCOUNT_JSON 和 GOOGLE_SHEET_ID")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def get_sheet_service():
    """建立 Google Sheets API 服務物件"""
    info = json.loads(SERVICE_ACCOUNT_JSON_STR)
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=credentials)
    return service


def load_inventory_from_sheet() -> Dict[str, Dict[str, str]]:
    """
    從 Google Sheet 讀取庫存資料。
    假設：
    第一列 = 標題
    A 欄 = 料號
    B 欄 = 品名
    C 欄 = Stock
    """
    service = get_sheet_service()
    sheet = service.spreadsheets()

    # 讀整張表的 A:C 欄位（依你實際表名把 Sheet1 改掉）
    range_name = "工作表1!A:C"
    result = sheet.values().get(spreadsheetId=SHEET_ID, range=range_name).execute()
    values: List[List[str]] = result.get("values", [])

    data: Dict[str, Dict[str, str]] = {}

    if not values or len(values) < 2:
        return data

    # 第 1 列是標題，從第 2 列開始
    for row in values[1:]:
        # 避免有空白列
        if len(row) < 1:
            continue

        part_no = str(row[0]).strip() if len(row) >= 1 else ""
        name = row[1].strip() if len(row) >= 2 else ""
        stock = row[2].strip() if len(row) >= 3 else ""

        if not part_no:
            continue

        data[part_no] = {
            "name": name,
            "stock": stock,
        }

    return data


def get_product_info_by_code(code: str) -> str:
    """輸入料號，從 Google Sheet 查出品名與庫存"""
    if not code:
        return "請輸入零件號碼。"

    code = str(code).strip()

    products = load_inventory_from_sheet()

    if code not in products:
        return f"查無此零件號碼：{code}"

    item = products[code]
    name = item.get("name", "")
    stock = item.get("stock", "")

    lines = [
        f"零件號碼：{code}",
        f"中文品名：{name}",
    ]
    if stock:
        lines.append(f"Stock：{stock}")

    return "\n".join(lines)


# ========= Flask & LINE Webhook =========
app = Flask(__name__)


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    print("Request body:", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature.")
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event: MessageEvent):
    user_text = event.message.text.strip()
    reply_text = get_product_info_by_code(user_text)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
