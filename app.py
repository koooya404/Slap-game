"""
尋問室ビンタ - Streamlit版
  ローカル実行: pip install -r requirements.txt && streamlit run app.py
  公開:        Streamlit Community Cloud でこのフォルダ(リポジトリ)を指定し、Main file path に app.py

ゲーム本体は同じフォルダの game.html(HTML5 Canvas)で、Streamlitから埋め込んで表示します。
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="尋問室ビンタ", page_icon="🖐️", layout="centered")

st.markdown(
    "<style>.block-container{padding-top:1.2rem;max-width:1000px}</style>",
    unsafe_allow_html=True,
)
st.title("🖐️ 尋問室ビンタ")
st.caption(
    "首の据わらない男の頭をひっぱたけ。命中 +30pt、制限時間30秒。"
    "手はマウス(指)より遅れてついてきます。クリック/タップでビンタ。"
)

html = (Path(__file__).parent / "game.html").read_text(encoding="utf-8")
components.html(html, height=660, scrolling=False)

with st.expander("遊び方"):
    st.markdown(
        "- **クリック / タップ**: ビンタ(振り抜いた瞬間の *手の位置* で判定)\n"
        "- **薄い輪っか**: 本当のマウス位置。手はこれより遅れて動く(遅れ量も揺れる)\n"
        "- **SPACE / Enter**: スタート・リトライ"
    )
