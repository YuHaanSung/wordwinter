import requests
import streamlit as st
from typing import Optional
from db import get_user, create_user, seed_opening_mastery

_PLATFORM_MAP = {
    "Chess.com": "CHESS_COM",
    "Lichess": "LICHESS",
}

_HEADERS = {"User-Agent": "OpeningFlex/1.0 (educational project)"}


def _verify_platform(platform_type: str, username: str) -> Optional[str]:
    """플랫폼 API로 닉네임 유효성 확인. 성공 시 canonical username 반환, 실패 시 None."""
    try:
        if platform_type == "CHESS_COM":
            url = f"https://api.chess.com/pub/player/{username.lower()}"
        else:
            url = f"https://lichess.org/api/user/{username}"

        resp = requests.get(url, headers=_HEADERS, timeout=6)
        if resp.status_code == 200:
            return resp.json().get("username", username)
        return None
    except Exception:
        return None


def render_home() -> None:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(
            """
            <div style='text-align:center;padding:2.5rem 0 1.5rem'>
                <span style='font-size:4rem'>♟</span>
                <h1 style='font-size:2.8rem;margin:0.2rem 0'>Opening Flex</h1>
                <p style='font-size:1.05rem;color:#888'>
                    체스 오프닝 약점 분석 &amp; 맞춤 훈련 플랫폼
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()

        platform_label = st.selectbox("플랫폼 선택", list(_PLATFORM_MAP.keys()))
        nickname = st.text_input(
            "닉네임 입력",
            placeholder="체스 플랫폼 닉네임을 입력하세요",
        )

        if st.button("분석 시작 →", type="primary", use_container_width=True):
            if not nickname.strip():
                st.error("닉네임을 입력해주세요.")
                return

            platform_type = _PLATFORM_MAP[platform_label]
            raw_name = nickname.strip()

            # Step 1: 플랫폼 API로 닉네임 인증
            with st.spinner(f"{platform_label}에서 사용자를 확인하는 중..."):
                canonical_name = _verify_platform(platform_type, raw_name)

            # API 실패 → DB에서 직접 조회 (오프라인 / 테스트 환경 대비)
            if canonical_name is None:
                with st.spinner("데이터베이스를 확인하는 중..."):
                    user = get_user(platform_type, raw_name)
                if user is None:
                    st.error(
                        f"{platform_label}에서 사용자를 찾을 수 없습니다. "
                        "닉네임을 다시 확인해주세요."
                    )
                    return
                # DB에서 찾은 경우 바로 이동
                st.session_state.user_id = user["user_id"]
                st.session_state.user_data = user
                st.session_state.current_page = "skill_tree"
                st.rerun()
                return

            # Step 2: DB에서 기존 사용자 조회
            with st.spinner("데이터베이스를 확인하는 중..."):
                user = get_user(platform_type, canonical_name)

            # Step 3: 신규 사용자 자동 등록
            if user is None:
                with st.spinner("신규 사용자를 등록하는 중..."):
                    user = create_user(platform_type, canonical_name)
                    if user:
                        seed_opening_mastery(user["user_id"])

                if user is None:
                    st.error("DB 연결에 실패했습니다. 잠시 후 다시 시도해주세요.")
                    return

            # Step 4: 스킬 트리로 이동
            st.session_state.user_id = user["user_id"]
            st.session_state.user_data = user
            st.session_state.current_page = "skill_tree"
            st.rerun()

        st.caption("처음 입력하시는 닉네임이면 자동으로 계정이 생성됩니다.")
