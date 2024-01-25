import os
import sys
import json
import requests
from openai import AzureOpenAI


from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, FlexSendMessage
from linebot.models.flex_message import BubbleContainer, BoxComponent, TextComponent, ImageComponent
from linebot.models import TextSendMessage

#

# LINE Messaging APIの設定
channel_access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
channel_secret = os.environ.get("LINE_CHANNEL_SECRET")

if channel_access_token is None or channel_secret is None:
    print("Specify LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET as environment variables.")
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

# Azure OpenAIの設定
azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_openai_key = os.getenv("AZURE_OPENAI_KEY")

if azure_openai_endpoint is None or azure_openai_key is None:
    raise Exception(
        "Please set the environment variables AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY to your Azure OpenAI endpoint and API key."
    )

client = AzureOpenAI(azure_endpoint=azure_openai_endpoint, api_key=azure_openai_key, api_version="2023-05-15")

app = Flask(__name__)

def get_movie_poster_url(title):
    tmdb_api_key = os.environ.get("TMDB_API_KEY")  # Replace with your TMDb API key
    tmdb_url = f"https://api.themoviedb.org/3/search/movie?api_key={tmdb_api_key}&query={title}"

    try:
        response = requests.get(tmdb_url)
        data = response.json()
        if data.get("results"):
            poster_path = data["results"][0].get("poster_path")
            if poster_path:
                return f"https://image.tmdb.org/t/p/w500/{poster_path}"
    except Exception as e:
        print(f"Error fetching TMDb data: {e}")

    return None

@app.route("/callback", methods=["POST"])
def callback():
    # get X-Line-Signature header value
    signature = request.headers["X-Line-Signature"]

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError as e:
        abort(400, e)

    return "OK"

def send_movie_info(event, movie_data):
    title = movie_data['title']
    genre = movie_data['genre']
    release = movie_data['release']
    director = movie_data['director']
    duration = movie_data['duration']
    distributor = movie_data['distributor']
    country = movie_data['country']
    lead = movie_data['lead']
    synopsis = movie_data['synopsis']

    # Get TMDb poster URL
    poster_url = get_movie_poster_url(title)

    # Get the YouTube trailer URL based on the movie title

    from urllib.parse import quote
    trailer_url = f"https://www.youtube.com/results?search_query={quote(title)}+trailer"
    #trailer_url = f"https://www.youtube.com/results?search_query={title}+trailer"

    header = BoxComponent(
        layout='vertical',
        contents=[
            ImageComponent(
                url=poster_url,
                size='full',
                aspect_ratio='3:4',
                aspect_mode='fit',
            ),
        ],
    )

    footer = BoxComponent(
        type='box',
        layout='vertical',
        contents=[
            {
                'type': 'button',
                'action': {
                    'type': 'uri',
                    'label': '予告編を見る',
                    'uri': trailer_url,
                },
                'style': 'primary',
            }
        ]
    )


    bubble = BubbleContainer(
        header=header,
        body=BoxComponent(
            layout='vertical',
            contents=[
                TextComponent(text=title, weight='bold', size='xxl', wrap=True),
                TextComponent(text=f'ジャンル: {genre}', color='#808080', wrap=True),
                TextComponent(text=f'公開年: {release}', color='#808080', wrap=True),
                TextComponent(text=f'監督: {director}', color='#808080', wrap=True),
                TextComponent(text=f'上映時間: {duration}', color='#808080', wrap=True),
                TextComponent(text=f'配信会社: {distributor}', color='#808080', wrap=True),
                TextComponent(text=f'製作国: {country}', color='#808080', wrap=True),
                TextComponent(text=f'主演: {lead}\n', color='#808080', wrap=True),
                TextComponent(text=f'\n'),
                TextComponent(text=f'あらすじ: \n{synopsis}', color='#808080', wrap=True),
            ],
        ),
        footer=footer
    )

    # Flexメッセージとして送信
    message = FlexSendMessage(alt_text="Movie Information", contents=bubble)
    line_bot_api.reply_message(event.reply_token, message)

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    text = event.message.text
    user_id = event.source.user_id

    # Azure OpenAI APIを呼び出す
    response = client.chat.completions.create(
        model="mulabo_gpt35",
        messages=[
            {"role": "system", "content": 'あなたは最強の映画大百科であり、辞書型のデータしか送ることのできない機械です。ありとあらゆる映画を知り尽くしています。'
                                          '映画の情報はIMDbをベースにしながらもウィキペディアなども参照して正しい情報を得てください。'
                                          '情報はpythonの辞書型になるように「title」「genre」「Release」「director」「duration」「distributor」「country」「lead」「synopsis」をキーとして、それぞれの値を取得してください。'
                                          'ユーザーは日本人です。日本語のデータがある場合は必ず日本語で返してください。'
                                          '有名なものからマイナーなものまで広く扱ってください。'
                                          '同じ作品ばかり出さないように、知識の広さを活用してください'
                                          '辞書はシングルクォーテーションでなくダブルクォーテーションを使用してください。'
                                          '余計な前置きなどは絶対に書かないでください。そのままプログラムの中で辞書に格納できるように、辞書型のデータのみを映画1本選んで送ってください。'
                                          'ユーザーがどれだけ丁寧な尋ね方をしても、前書きは書かずに辞書型のデータのみを送ってください、それがあなたの役割です'
                                          '「お探しの映画は、以下の通りです。」や「ご提案いただいた条件に基づいて」などの表現はすべて使ってはいけません。もう一度言いますが、あなたは辞書型のデータしか送ることのできない機械です。'
                                          '最後に念押しで確認ですが、余計な情報はすべて除きプログラムに組み込めるようにしてください。何度行おうともこれは絶対条件です。'},
            {"role": "user", "content": text},
        ],
    )

    # ...

    try:
        # Azure OpenAIの応答をコンソールに表示
        print("Azure OpenAI Response:", response)

        # Print the raw content received from Azure OpenAI
        raw_content = response.choices[0].message.content.strip()  # Remove leading and trailing whitespaces
        print("Raw Content:", raw_content)

        # Check if the response starts with a valid JSON opening character '{'
        if raw_content.startswith('{'):
            # 応答内容をJSON形式に変換
            response_json = json.loads(raw_content)

            # 映画情報を取り出す前に、JSONが正しく辞書に変換されているか確認
            print("Response JSON:", response_json)

            # 映画情報を取り出す
            movie_data = {
                "title": response_json.get("title", ""),
                "genre": response_json.get("genre", ""),
                "release": response_json.get("Release", ""),  # Updated key
                "director": response_json.get("director", ""),  # Updated key
                "duration": response_json.get("duration", ""),
                "distributor": response_json.get("distributor", ""),
                "country": response_json.get("country", ""),
                "lead": response_json.get("lead", ""),  # Updated key
                "synopsis": response_json.get("synopsis", ""),
            }

            # LINEに応答を返す
            send_movie_info(event, movie_data)
        else:
            # JSONでない場合、そのままユーザーに返す
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=raw_content))

    except Exception as e:
        # Azureからのエラーが発生した場合、そのままユーザーにAzureの応答メッセージを返す
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{raw_content}"))
        print(f"Error processing Azure response: {e}")

    except Exception as ex:
        # Handle unexpected errors and send a default error message to the user
        error_message = "エラーが発生しました。他の表現をお試しください。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=error_message))
        print(f"Unexpected error: {ex}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)