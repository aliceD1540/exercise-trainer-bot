from dotenv import load_dotenv
import logging
import os
from utils.bsky_util import BlueskyUtil
from datetime import datetime, timedelta, timezone
import google.generativeai as genai
import requests
import PIL.Image

load_dotenv(".env")
logging.basicConfig(
    level=logging._nameToLevel[os.getenv("LOG_LEVEL", "FATAL")],
    format="%(asctime)s %(name)s %(levelname)s:%(message)s",
    filename="./debug.log",
)
logger = logging.getLogger(__name__)

bsky_util = BlueskyUtil()
bsky_util.load_session()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")


def download_image(post_data):
    # tmp_imgフォルダの準備
    if not os.path.exists("tmp_img"):
        os.makedirs("tmp_img")
    else:
        # フォルダ内の既存ファイルを削除
        for f in os.listdir("tmp_img"):
            os.remove(os.path.join("tmp_img", f))
    # 画像のダウンロード
    img_count = 0
    if "images" in post_data:
        for img_url in post_data["images"]:
            response = requests.get(img_url)
            if response.status_code == 200:
                # tmp_imgフォルダに画像を保存
                with open(f"tmp_img/{img_count:02d}.jpg", "wb") as f:
                    f.write(response.content)
                img_count += 1


def request_gemini_cli(post_data):
    with open("rules.md", "r", encoding="utf-8") as f:
        rules = f.read()

    prompt = rules + "\n\n" + post_data["text"]

    print("--- Prompt for Gemini ---")
    # print(prompt)

    # 画像を読み込む
    image_folder = "tmp_img"
    image_files = [
        os.path.join(image_folder, f) for f in sorted(os.listdir(image_folder))
    ]
    images = [PIL.Image.open(img_file) for img_file in image_files]

    # プロンプトと画像を結合
    prompt_parts = [prompt]
    if images:
        prompt_parts.extend(images)

    response = model.generate_content(prompt_parts)

    print("--- Gemini Response ---")
    response_text = response.text
    if len(response_text) > 300:
        # 300文字を超えた場合は、最後の句点（。）で切り詰める
        response_text = response_text[:300]
        last_period_index = response_text.rfind("。")
        if last_period_index != -1:
            response_text = response_text[: last_period_index + 1]

    print(response_text)

    return response_text


# 現在時刻を5分単位に丸めて、5分前と10分前を計算
now_utc = datetime.now(timezone.utc)
now_rounded = now_utc.replace(minute=(now_utc.minute // 5) * 5, second=0, microsecond=0)
since, until = [(now_rounded - timedelta(minutes=m)).isoformat() for m in [5, 10]]
# テスト用に期間を3時間に設定
# since = (now_rounded - timedelta(hours=3)).isoformat()
# until = now_rounded.isoformat()

posts = bsky_util.search_posts(
    query="#青空筋トレ部",
    limit=10,
    did=os.getenv("CHECK_BSKY_DID"),
    since=since,
    until=until,
)

for post in posts.posts:
    post_data = {
        "text": post.record.text,
        "created_at": post.record.created_at,
        "author": post.author.did,
        "uri": post.uri,
    }
    if hasattr(post, "embed"):
        if hasattr(post.embed, "images"):
            post_data["images"] = [img.fullsize for img in post.embed.images]

    download_image(post_data)
    text = request_gemini_cli(post_data)
    bsky_util.post_reply(message=text, uri=post.uri, cid=post.cid)
