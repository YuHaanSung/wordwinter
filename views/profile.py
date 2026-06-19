import streamlit as st
from datetime import datetime
from db import get_user_by_id, get_mastery_with_eco
from views.stats import _tier_info

_TIER_LABELS = {"FREE": "🆓 무료", "PRO": "⭐ 프로"}


def _format_created_at(raw: str | None) -> str:
    if not raw:
        return "-"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y년 %m월 %d일")
    except Exception:
        return raw


def render_profile() -> None:
    st.markdown("# 👤 내 정보")

    if not st.session_state.get("user_id"):
        st.warning("먼저 홈 화면에서 닉네임을 입력해주세요.")
        if st.button("홈으로 이동"):
            st.session_state.current_page = "home"
            st.rerun()
        return

    user_id = st.session_state.user_id
    fresh_user = get_user_by_id(user_id)
    if fresh_user:
        st.session_state.user_data = fresh_user
    user = st.session_state.user_data or {}

    platform_type = user.get("platform_type", "")
    platform_label = "Chess.com" if platform_type == "CHESS_COM" else "Lichess"
    tier_label = _TIER_LABELS.get(user.get("tier", "FREE"), user.get("tier", "FREE"))

    # ── 프로필 카드 ──────────────────────────────────────────────────────────
    with st.container(border=True):
        col_main, col_btn = st.columns([4, 1])
        with col_main:
            st.markdown(f"## {user.get('chess_platform_id', '')}")
            st.caption(f"{platform_label}  ·  {tier_label}  ·  가입일 {_format_created_at(user.get('created_at'))}")
        with col_btn:
            if st.button("🔄 새로고침", use_container_width=True):
                st.rerun()

    st.divider()

    # ── 핵심 지표 ────────────────────────────────────────────────────────────
    rows = get_mastery_with_eco(user_id) or []
    total = len(rows)
    mastered = sum(1 for r in rows if r.get("is_mastered"))

    score = user.get("total_knowledge_score", 0)
    score_tier_label, *_rest = _tier_info(score)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("지식 점수", score)
    c2.metric("티어", score_tier_label)
    c3.metric("분석된 오프닝", total)
    c4.metric("마스터 완료", f"{mastered}/{total}" if total else "0/0")

    st.divider()

    # ── 계정 관리 ────────────────────────────────────────────────────────────
    st.markdown("### ⚙️ 계정")

    if st.button("🚪 다른 계정으로 전환 / 로그아웃", type="secondary"):
        st.session_state.user_id = None
        st.session_state.user_data = None
        st.session_state.selected_eco = None
        st.session_state.current_page = "home"
        st.rerun()
