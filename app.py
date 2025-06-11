import streamlit as st
import os
import requests
from datetime import datetime
import openai
from dotenv import load_dotenv


# ---- 環境変数の読み込み ----
load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- 入力UI ---
category = st.selectbox("お店カテゴリ", ["イタリアン", "和食", "中華", "フレンチ", "居酒屋", "その他"])
avg_price = st.number_input("平均メニュー価格（円）", value=1200)
area = st.text_input("お店のエリア")
alcohol = st.text_input("お酒ペアリング")
date = st.date_input("日付")
ingredient_field = st.text_area("食材名・量・価格（例: トマト2個150円, ...）")

if st.button("レシピを検索"):
    date_str = date.strftime("%Y/%m/%d")

    # --- OpenAI用プロンプト生成 ---
    payload = [
        {"role": "system", "content": 
            "あなたは業務用レシピ提案のプロAIシェフです。与えられた食材と店舗条件から、季節・価格・エリアも考慮し、最適なレシピを日本語で出力してください。"
        },
        {"role": "user", "content": f"""
【タスク】
- 食材: {ingredient_field}を使った お店カテゴリ: {category}向けの新メニューを**必ず3品**考えてください。平均価格: {avg_price}円、エリア: {area}、季節性: {date_str}を考慮してメニューを検索し、提案すること。お酒ペアリング: {alcohol}に指定のある場合は、ペアリングを考えてメニュー提案をしてください。参照した情報のURLも提示してください。

【制約・出力形式】
- 各メニューに「料理名」「説明（特徴やおすすめポイント）」「材料と分量」「調理方法（3〜5ステップ）」「1人前の原価計算」「販売価格の目安（原価率30%想定）」を**必ず**記載
- 出力はmarkdown形式、見やすく
- ※「レシピ数」は3品で固定

【追加条件】
- お店カテゴリ: {category}
- 平均価格: {avg_price}円
- エリア: {area}
- お酒ペアリング: {alcohol}
- 日付: {date_str}
- 食材: {ingredient_field}

【出力例】
### 1. 太刀魚のアクアパッツァ
説明：……
ペアリング提案：……
材料：……
調理方法：
1.
2.
3.
原価：……
販売価格目安：……
参照URL：……
---
"""}
    ]

    # --- OpenAI API呼び出し ---
    response = client.chat.completions.create(
        model="gpt-4o-search-preview-2025-03-11",
        messages=payload,
        response_format={"type": "text"}
    )

    # --- 結果をそのままmarkdownで表示 ---
    result_text = response.choices[0].message.content
    st.markdown(result_text)

