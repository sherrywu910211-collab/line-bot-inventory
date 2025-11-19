import os
import pandas as pd
from flask import Flask, request, abort

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 從環境變數讀取金鑰（安全做法）
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

if not CHANNEL_SECRET or not CHANNEL_ACCESS_TOKEN:
    raise ValueError("請先在 Render 設定環境變數 LINE_CHANNEL_SECRET 和 LINE_CHANNEL_ACCESS_TOKEN")

# 這裡暫時先用「程式內建一個小字典」當假資料
# 之後再把它改成讀 Excel 或 Google Sheet
PRODUCTS = {
    "123": {"name": "測試品項A", "stock": "10"},
    "456": {"name": "測試品項B", "stock": "5"},
}

def get_product_info_by_code(code: str) -> str:
    if not code:
        return "請輸入零件號碼。"

    code = str(code).strip()

    if code not in PRODUCTS:
        return f"查無此零件號碼：{code}"

    item = PRODUCTS[code]
    name = item.get("name", "")
    stock = item.get("stock", "")

    lines = [
        f"零件號碼：{code}",
        f"中文品名：{name}",
    ]
    if stock:
        lines.append(f"Stock：{stock}")

    return "\n".join(lines)

app = Flask(__name__)

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

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
