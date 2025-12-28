import streamlit as st
import json
import os
import pandas as pd
from typing import Dict, List

# --- 設定 ---
# region_master.json ファイルのパスをプロジェクトのルートに設定
# 実行時の環境に合わせてこのパスを調整してください。
FILE_PATH = os.path.join(os.path.dirname(__file__), "region_master.json")

# --- 関数: データの読み込みと保存 ---

@st.cache_data
def load_region_data() -> Dict[str, List[str]]:
    """JSONファイルから地域データを読み込む"""
    if not os.path.exists(FILE_PATH):
        st.error(f"エラー: 地域マスタファイルが見つかりません: {FILE_PATH}")
        return {}
    
    try:
        with open(FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        st.error(f"ファイルの読み込み中にエラーが発生しました: {e}")
        return {}

def save_region_data(data: Dict[str, List[str]]):
    """JSONファイルに地域データを書き込む"""
    try:
        # NOTE: このファイル書き込みは、Streamlitの実行環境によっては権限がない場合があります。
        with open(FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        st.toast("✅ データを保存しました！", icon="🎉")
        
        # キャッシュをクリアしてデータを再ロード
        st.cache_data.clear()
        st.rerun() 
    except Exception as e:
        st.error(f"ファイルの保存中にエラーが発生しました: {e}")


# --- Streamlit アプリケーション本体 ---

def app():
    st.set_page_config(layout="wide", page_title="E-Basho 地域マスタ管理")
    
    st.title("🏡 E-Basho 地域マスタデータ管理")
    st.markdown("ここでは、動的通知に使用する地域名と、ユーザーが入力する表記ゆれのデータを管理します。")
    
    # データをセッションステートに格納
    if 'region_data' not in st.session_state:
        st.session_state.region_data = load_region_data()

    data = st.session_state.region_data
    
    if not data:
        st.warning("データが空です。以下のフォームから新しいデータを追加してください。")
    
    # --- サイドバー (機能メニュー) ---
    st.sidebar.header("操作メニュー")
    
    # --- 1. データの一覧表示 ---
    st.header("1. 現在の地域マスタ一覧")
    
    # 表示用にデータを整形
    df_data = []
    for formal_name, aliases in data.items():
        df_data.append({
            "正式名称 (DB Key)": formal_name,
            "表記ゆれ/別名 (Aliases)": ", ".join(aliases),
            "別名数": len(aliases)
        })
    
    if df_data:
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # --- 2. 新規地域の追加 ---
    st.sidebar.subheader("新規地域の追加")
    with st.sidebar.form("add_new_region"):
        new_formal_name = st.text_input("正式名称 (例: 大阪府)", key="new_formal_name")
        new_alias_input = st.text_input("表記ゆれ (カンマ区切り)", key="new_alias_input")
        submitted = st.form_submit_button("新規追加して保存")

        if submitted:
            if not new_formal_name:
                st.error("正式名称は必須です。")
            elif new_formal_name in data:
                st.error("この正式名称は既に存在します。")
            else:
                new_aliases = [a.strip() for a in new_alias_input.split(',') if a.strip()]
                
                # 新しいデータを追加
                new_data = data.copy()
                new_data[new_formal_name] = new_aliases
                
                # 保存実行
                save_region_data(new_data)


    # --- 3. 既存データの編集 (サイドバー) ---
    st.sidebar.subheader("既存データの編集/追加")
    
    # 編集対象の選択
    region_options = [""] + list(data.keys())
    selected_region = st.sidebar.selectbox("編集する正式名称を選択", region_options, key="selected_region")
    
    if selected_region:
        current_aliases_str = ", ".join(data.get(selected_region, []))
        
        with st.sidebar.form("edit_aliases"):
            st.markdown(f"**{selected_region}** の現在の別名:")
            edited_alias_input = st.text_area(
                "別名リスト (カンマ区切りで入力)", 
                value=current_aliases_str,
                height=100,
                key="edited_alias_input"
            )
            update_submitted = st.form_submit_button(f"{selected_region} の別名を更新")

            if update_submitted:
                edited_aliases = [a.strip() for a in edited_alias_input.split(',') if a.strip()]
                
                # データを更新
                data[selected_region] = edited_aliases
                
                # 保存実行
                save_region_data(data)

if __name__ == "__main__":
    app()