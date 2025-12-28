import streamlit as st
import sqlite3
import pandas as pd


DB_PATH = "address.db"

# -------------------------
# DB 接続ヘルパー
# -------------------------
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------
# 都道府県一覧
# -------------------------
def get_prefectures(conn):
    return conn.execute("SELECT * FROM prefectures ORDER BY id").fetchall()


# -------------------------
# 市区町村取得
# -------------------------
def get_cities(conn, prefecture_id):
    return conn.execute(
        "SELECT * FROM cities WHERE prefecture_id = ? ORDER BY id",
        (prefecture_id,)
    ).fetchall()


# -------------------------
# synonym取得
# -------------------------
def get_synonyms(conn, city_id):
    return conn.execute(
        "SELECT * FROM synonyms WHERE city_id = ? ORDER BY id",
        (city_id,)
    ).fetchall()


# -------------------------
# synonym追加
# -------------------------
def add_synonym(conn, city_id, synonym):
    conn.execute(
        "INSERT INTO synonyms (city_id, synonym, type) VALUES (?, ?, ?)",
        (city_id, synonym, "manual")
    )
    conn.commit()


# -------------------------
# synonym削除
# -------------------------
def delete_synonym(conn, synonym_id):
    conn.execute("DELETE FROM synonyms WHERE id = ?", (synonym_id,))
    conn.commit()


# ============================================================
# Streamlit UI ここから
# ============================================================
st.set_page_config(page_title="住所マスタ管理", layout="wide")
st.title("📍 住所マスタ管理（日本全国）")

conn = get_connection()


# ------------------------------------------
# 1. 都道府県を選択
# ------------------------------------------
st.subheader("① 都道府県を選択")

prefs = get_prefectures(conn)
pref_names = {p["name"]: p["id"] for p in prefs}

selected_pref = st.selectbox("都道府県を選択", list(pref_names.keys()))

if selected_pref:
    pref_id = pref_names[selected_pref]

    # ------------------------------------------
    # 2. 市区町村一覧
    # ------------------------------------------
    st.subheader(f"② {selected_pref} の市区町村")

    cities = get_cities(conn, pref_id)
    city_names = {c["name"]: c["id"] for c in cities}

    selected_city = st.selectbox("市区町村を選択", list(city_names.keys()))

    if selected_city:
        city_id = city_names[selected_city]

        # ------------------------------------------
        # 3. 表記ゆれ（synonyms）一覧
        # ------------------------------------------
        st.subheader(f"③ {selected_city} の表記ゆれデータ")

        syns = get_synonyms(conn, city_id)
        df_syn = pd.DataFrame(syns)

        if len(df_syn) > 0:
            st.dataframe(df_syn, use_container_width=True)
        else:
            st.info("まだ表記ゆれがありません。")

        # ------------------------------------------
        # 4. synonym 追加
        # ------------------------------------------
        st.markdown("### ➕ 表記ゆれを追加")

        new_syn = st.text_input("新しい表記ゆれ（例：としま、ﾄｼﾏ）")

        if st.button("追加する"):
            if new_syn.strip() != "":
                add_synonym(conn, city_id, new_syn.strip())
                st.success(f"追加しました: {new_syn}")
                st.rerun()
            else:
                st.error("表記ゆれを入力してください。")

        # ------------------------------------------
        # 5. synonym 削除
        # ------------------------------------------
        st.markdown("### 🗑️ 表記ゆれを削除")

        syn_options = {f"{row['synonym']} (id={row['id']})": row["id"] for row in syns}

        if len(syn_options) > 0:
            syn_to_delete = st.selectbox("削除する項目を選択", list(syn_options.keys()))
            if st.button("削除する"):
                delete_synonym(conn, syn_options[syn_to_delete])
                st.warning(f"削除しました: {syn_to_delete}")
                st.rerun()
