import streamlit as st
from collections import defaultdict
from db import get_mastery_with_eco, upsert_openings, get_user_by_id
from analysis import analyze_games, _fetch_recent_games

_THRESHOLD_OPTIONS = {
    "10수 이내": 10,
    "15수 이내": 15,
    "20수 이내 (기본)": 20,
    "25수 이내": 25,
    "30수 이내": 30,
    "제한 없음": 9999,
}

_BLINK_CSS = """
<style>
@keyframes blink-weak-anim { 0%, 100% { opacity: 1; } 50% { opacity: 0.25; } }
.blink-weak { animation: blink-weak-anim 1.4s ease-in-out infinite; display: inline-block; }
</style>
"""


def _render_analysis_panel(nickname: str, user_id: str, platform_type: str) -> None:
    """오프닝 분석 패널 — Chess.com 게임을 가져와 이른 패배 오프닝을 집계."""
    with st.expander("🔍 오프닝 분석 (Chess.com 게임 기반)", expanded=True):
        st.markdown(
            "최근 Chess.com 게임에서 **지정한 수 이내에 패배한 오프닝**을 자동 분석합니다. "
            "결과는 스킬 트리에 즉시 반영됩니다."
        )

        if platform_type != "CHESS_COM":
            st.warning("현재 Chess.com 계정만 게임 분석을 지원합니다.")
            return

        col1, col2 = st.columns([2, 1])
        with col1:
            threshold_label = st.selectbox(
                "패배 기준 수",
                list(_THRESHOLD_OPTIONS.keys()),
                index=2,
                help="이 수 이하로 게임이 끝났을 때만 오프닝 약점으로 집계합니다.",
            )
        with col2:
            months = st.selectbox("분석 범위", ["최근 1개월", "최근 2개월"], index=1)

        move_threshold = _THRESHOLD_OPTIONS[threshold_label]
        max_months = 1 if months == "최근 1개월" else 2

        if st.button("분석 시작", type="primary", use_container_width=True):
            # ── 게임 가져오기 (한 번만 호출, 분석에 재사용) ──────────────
            with st.spinner(f"Chess.com에서 최근 {max_months}개월 게임을 가져오는 중..."):
                all_games = _fetch_recent_games(nickname, max_months)

            if not all_games:
                st.error(
                    f"**{nickname}** 의 게임을 가져오지 못했습니다. "
                    "Chess.com 닉네임이 정확한지 확인하거나 잠시 후 다시 시도해주세요."
                )
                return

            # ── 이른 패배 분석 ───────────────────────────────────────────
            with st.spinner(f"{len(all_games)}게임 분석 중 ({threshold_label} 기준)..."):
                results = analyze_games(nickname, all_games, move_threshold=move_threshold)

            st.caption(f"총 {len(all_games)}게임 로드됨")

            if not results:
                st.info(
                    f"**{threshold_label}** 이내 패배 기록이 없습니다. "
                    "기준 수를 높이거나 분석 범위를 늘려보세요."
                )
                return

            # ── 분석 결과 미리보기 ────────────────────────────────────────
            total_losses = sum(r["loss_count"] for r in results)
            st.markdown(
                f"**{len(results)}개 오프닝**에서 총 **{total_losses}회** 이른 패배 발견"
            )

            preview_data = [
                {
                    "오프닝": f"{r['name']} ({r['eco_code']})",
                    "패밀리": r["family"],
                    "패배 횟수": r["loss_count"],
                }
                for r in results[:10]
            ]
            import pandas as pd
            st.dataframe(pd.DataFrame(preview_data), use_container_width=True, hide_index=True)

            # ── DB 저장 ────────────────────────────────────────────────────
            with st.spinner("분석 결과를 저장하는 중..."):
                ok = upsert_openings(user_id, results)

            if ok:
                st.success("스킬 트리가 업데이트됐습니다!")
                st.rerun()
            else:
                st.error("DB 저장에 실패했습니다.")


def _render_opening_row(o: dict) -> None:
    """오프닝 한 줄 렌더링."""
    eco_ref = o.get("eco_reference") or {}
    eco_code = o.get("eco_code", "")
    name = eco_ref.get("name") or eco_code
    is_mastered: bool = o.get("is_mastered", False)
    loss_count: int = o.get("loss_count", 0)
    streak: int = o.get("defense_streak", 0)
    last_seq: str = o.get("last_lost_sequence") or ""

    icon = "🟢" if is_mastered else '<span class="blink-weak">🔴</span>'
    c1, c2, c3 = st.columns([4, 3, 2])

    with c1:
        st.markdown(f"{icon} **{name}**", unsafe_allow_html=True)
        st.caption(f"ECO: `{eco_code}`")
        if last_seq:
            st.caption(f"최근 패배 기보: `{last_seq}`")

    with c2:
        st.markdown(f"패배 횟수: **{loss_count}**회")
        streak_bar = "🟦" * streak + "⬜" * (3 - streak)
        st.markdown(f"방어 연속: {streak_bar} **{streak}/3**")

    with c3:
        if is_mastered:
            st.success("마스터 완료!")
        else:
            if st.button(
                "훈련 시작",
                key=f"train_{eco_code}",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.selected_eco = eco_code
                st.session_state.current_page = "training"
                st.rerun()

    st.divider()


def render_skill_tree() -> None:
    st.markdown(_BLINK_CSS, unsafe_allow_html=True)

    if not st.session_state.get("user_id"):
        st.warning("먼저 홈 화면에서 닉네임을 입력해주세요.")
        if st.button("홈으로 이동"):
            st.session_state.current_page = "home"
            st.rerun()
        return

    # 훈련 중 직접 갱신된 지식 점수/스킬 등 최신 값으로 새로고침
    fresh_user = get_user_by_id(st.session_state.user_id)
    if fresh_user:
        st.session_state.user_data = fresh_user

    user = st.session_state.user_data or {}
    nickname = user.get("chess_platform_id", "")
    platform_type = user.get("platform_type", "")
    platform_label = "Chess.com" if platform_type == "CHESS_COM" else "Lichess"

    st.markdown("# ♟ 오프닝 스킬 트리")
    st.markdown(f"**{nickname}** ({platform_label}) 님의 약점 오프닝 목록입니다.")

    # ── 분석 패널 ──────────────────────────────────────────────────────────────
    _render_analysis_panel(nickname, st.session_state.user_id, platform_type)
    st.divider()

    # ── 스킬 트리 조회 ────────────────────────────────────────────────────────
    with st.spinner("오프닝 데이터를 불러오는 중..."):
        rows = get_mastery_with_eco(st.session_state.user_id)

    if rows is None:
        st.error("DB 연결에 실패했습니다.")
        return
    if not rows:
        st.info("아직 분석된 오프닝이 없습니다. 위 **오프닝 분석** 패널에서 게임을 분석해보세요.")
        return

    # 사이드바에 마스터 현황 표시용으로 저장
    st.session_state["mastered_count"] = sum(1 for r in rows if r.get("is_mastered"))
    st.session_state["total_openings_count"] = len(rows)

    # ── family 기준 그룹화 → 렌더링 ──────────────────────────────────────────
    groups: dict[str, list] = defaultdict(list)
    for row in rows:
        family = (row.get("eco_reference") or {}).get("family") or "기타"
        groups[family].append(row)

    # 패배 많은 그룹 먼저
    sorted_groups = sorted(
        groups.items(),
        key=lambda kv: sum(o.get("loss_count", 0) for o in kv[1]),
        reverse=True,
    )

    for family, openings in sorted_groups:
        mastered = sum(1 for o in openings if o.get("is_mastered"))
        total_losses = sum(o.get("loss_count", 0) for o in openings)
        label = f"**{family}** — {mastered}/{len(openings)} 마스터 · 총 패배 {total_losses}회"

        with st.expander(label, expanded=True):
            # 패배 많은 순 정렬
            for o in sorted(openings, key=lambda x: x.get("loss_count", 0), reverse=True):
                _render_opening_row(o)
