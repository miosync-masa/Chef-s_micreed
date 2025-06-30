import streamlit as st
import pandas as pd
import os
import requests
from datetime import datetime
import openai

# ---- 環境変数の読み込み ----
load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.title("売上ランキング抽出AI for 飲食店")

# 除外アイテムをマルチセレクトやテキスト入力で指定
exclude_items = st.text_input(
    "新メニューAI提案で除外したい食材・既存商品名をカンマ区切りで入力（例: 牛たん,麦飯,とろろ,テールスープ,牛たん丼）",
    value="牛たん,麦飯,とろろ,テールスープ,牛たん丼"
).replace(" ", "").split(",")

# or
# exclude_items = st.multiselect(
#     "新メニューAIで除外したい商品・食材を選んでください",
#     ["牛たん", "麦飯", "とろろ", "テールスープ", "牛たん丼", "サーモン", "ポテサラ", ...],
#     default=["牛たん", "麦飯", "とろろ", "テールスープ", "牛たん丼"]
# )

exclude_text = "、".join(exclude_items)

area = st.text_input("お店のエリア（例：渋谷、仙台駅前など）")
category = st.selectbox(
    "お店カテゴリ",
    ["イタリアン", "和食", "中華", "フレンチ", "居酒屋", "串焼き（牛タン）", "その他"]
)
uploaded_file = st.file_uploader("Excelファイルをアップロードしてください", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    st.write("📋 アップロードされたデータプレビュー")
    st.dataframe(df.head())

    # --- 会計日時から時間帯（ランチ/ディナー/その他）を自動判定 ---
    def classify_time(row):
        try:
            hour = pd.to_datetime(row["会計日時"]).hour
        except Exception:
            return "不明"
        if 11 <= hour < 15:
            return "ランチ"
        elif 17 <= hour < 22:
            return "ディナー"
        else:
            return "その他"

    df["時間帯"] = df.apply(classify_time, axis=1)

    # --- 時間帯ごとにランキング表示 ---
    for time_zone in ["ランチ", "ディナー"]:
        sub = df[df["時間帯"] == time_zone]
        st.write(f"## ⏰ {time_zone}タイム売上ランキング")
        if len(sub) == 0:
            st.info(f"{time_zone}タイムのデータはありません。")
            continue
        ranking = (
            sub.groupby(['分類名称', 'メニュー名称'])['販売金額(税込)']
            .sum().reset_index()
            .sort_values(['分類名称', '販売金額(税込)'], ascending=[True, False])
        )
        st.dataframe(ranking)

    # --- AIプロンプト用ランキングテキストはループ外で作る！ ---
    lunch_ranking_text = (
        df[df["時間帯"] == "ランチ"]
        .groupby(['分類名称', 'メニュー名称'])['販売金額(税込)']
        .sum().reset_index()
        .sort_values(['分類名称', '販売金額(税込)'], ascending=[True, False])
        .head(10)
        .to_string(index=False)
    )

    dinner_ranking_text = (
        df[df["時間帯"] == "ディナー"]
        .groupby(['分類名称', 'メニュー名称'])['販売金額(税込)']
        .sum().reset_index()
        .sort_values(['分類名称', '販売金額(税込)'], ascending=[True, False])
        .head(10)
        .to_string(index=False)
    )
    
    # --- 全体ランキングも表示（もとの仕様） ---
    st.write("🏆 分類別メニュー売上ランキング（全時間帯・合計金額順）")
    overall_ranking = (
        df.groupby(['分類名称', 'メニュー名称'])['販売金額(税込)']
        .sum().reset_index()
        .sort_values(['分類名称', '販売金額(税込)'], ascending=[True, False])
    )
    st.dataframe(overall_ranking)

    ranking_summary = overall_ranking.head(20).to_string(index=False)  # 全体上位20件を文字列化

    # --- ボタン①：AI要約 ---
    if st.button("AIでお店の方向性を要約する"):
        payload = [
            {"role": "system", "content":
                "あなたは業務用レストラン分析とレシピ開発に長けたプロAIシェフです。"
            },
            {"role": "user", "content": f"""
下記の売上ランキングを参考に、**Markdownの番号付きリスト**で次の観点ごとに現場分析コメントをまとめてください。

1. 主役商品・カテゴリ：どの分類やメニューが主力か？
2. 時間帯ごとの傾向：ランチとディナーで売れ筋や客層に違いはあるか？
3. 副菜/おつまみ/デザートの強み：サイド・つまみ・甘味の特徴や人気ポイント
4. 利用シーン・顧客層：どんな使われ方（飲み／食事／一人／グループ等）、どんな層が中心か？
5. 総合評価・戦略アドバイス：この店の強み・今後の方向性や課題があれば具体的に

お酒の売れ筋もコメントに必ず入れてください。

【ランチランキング】

{lunch_ranking_text}

【ディナーランキング】
{dinner_ranking_text}

【全体傾向（参考）】
{ranking_summary}
            """}
        ]
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=payload,
            response_format={"type": "text"}
        )
        direction_summary = response.choices[0].message.content
        st.session_state['direction_summary'] = direction_summary  # ←ここで保存
        st.markdown("### 🧭 お店のメニュー方向性・現場指針（AI要約）")
        st.markdown(direction_summary)

    # --- ボタン②：要約が保存されていれば、新メニューAI
    if 'direction_summary' in st.session_state:
        if st.button("この方向性で新メニューAI提案を出す"):
            direction_summary = st.session_state['direction_summary']
            recipe_prompt = f"""
あなたは業務用レシピ提案のプロAIシェフです。
下記のお店の方向性・カテゴリ・エリアにぴったり合う、“新しい売れ筋メニュー”を必ず3品、実務レベルで考案してください。新メニュー提案時は、以下の食材や既存商品を必ず除外してください：
【除外リスト】{exclude_text}

【お店の方向性・指針】
{direction_summary}
【お店カテゴリ】{category}
【エリア】{area}

各メニューは以下の情報を必ず含めてください：
- 料理名
- 説明（特徴やおすすめポイント）
- 材料と分量
- 調理方法（3〜5ステップ）
- 1人前の原価計算
- 販売価格の目安（原価率30%想定）
- 可能ならWebで参考にしたURL（公式やレシピサイト等）

出力はmarkdown形式で。必ず3品、独自性や現場に刺さる新提案を重視してください。
"""
            recipe_response = client.chat.completions.create(
                model="gpt-4o-search-preview-2025-03-11",
                messages=[
                    {"role": "system", "content": "あなたは業務用レシピ提案のプロAIシェフです。"},
                    {"role": "user", "content": recipe_prompt}
                ]
            )
            recipe_text = recipe_response.choices[0].message.content
            st.markdown("### 🍳 このお店に最適な新メニューAI提案（3品）")
            st.markdown(recipe_text)
else:
    st.info("売上ランキングを出すには、まずExcelファイルをアップロードしてください。")
