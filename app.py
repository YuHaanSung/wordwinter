import streamlit as st
from views.home import render_home
from views.skill_tree import render_skill_tree
from views.training import render_training
from views.stats import render_stats
from views.recommendations import render_recommendations
from views.profile import render_profile

_NAV_ITEMS = [
    ("home", "🏠 홈"),
    ("skill_tree", "♟️ 오프닝연습"),
    ("stats", "📊 통계"),
    ("recommendations", "🔗 사이트추천"),
    ("profile", "👤 내 정보"),
]


def _init_session() -> None:
    defaults: dict = {
        "current_page": "home",
        "user_id": None,
        "selected_eco": None,
        "user_data": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _render_topbar() -> None:
    title_col, info_col = st.columns([3, 2])
    with title_col:
        st.markdown("## ♟ Opening Flex")
    with info_col:
        if st.session_state.user_data:
            u = st.session_state.user_data
            platform = "Chess.com" if u.get("platform_type") == "CHESS_COM" else "Lichess"
            mastered = st.session_state.get("mastered_count")
            total = st.session_state.get("total_openings_count")
            mastery_txt = f" · 🏆 {mastered}/{total}" if mastered is not None and total is not None else ""
            st.markdown(
                f"<div style='text-align:right;padding-top:8px;color:#94a3b8;font-size:13px'>"
                f"<b>{u.get('chess_platform_id', '')}</b> · {platform} · {u.get('tier', 'FREE')} "
                f"· 🧠 {u.get('total_knowledge_score', 0)}점{mastery_txt}"
                f"</div>",
                unsafe_allow_html=True,
            )

    current = st.session_state.current_page
    # 훈련 페이지는 '오프닝연습'의 하위 흐름이므로 같이 활성 표시
    active_key = "skill_tree" if current == "training" else current

    cols = st.columns(len(_NAV_ITEMS))
    for col, (key, label) in zip(cols, _NAV_ITEMS):
        is_active = (key == active_key)
        if col.button(
            label,
            use_container_width=True,
            type="primary" if is_active else "secondary",
            key=f"nav_{key}",
        ):
            st.session_state.current_page = key
            st.rerun()

    st.divider()


def main() -> None:
    st.set_page_config(
        page_title="Opening Flex",
        page_icon="♟",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _init_session()
    _render_topbar()

    page: str = st.session_state.current_page
    if page == "home":
        render_home()
    elif page == "skill_tree":
        render_skill_tree()
    elif page == "training":
        render_training()
    elif page == "stats":
        render_stats()
    elif page == "recommendations":
        render_recommendations()
    elif page == "profile":
        render_profile()


if __name__ == "__main__":
    main()
