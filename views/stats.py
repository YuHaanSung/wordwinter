import streamlit as st
import pandas as pd
from db import get_mastery_with_eco, get_user_by_id

# (점수 하한, 티어 이름, 그라데이션 시작색, 그라데이션 끝색)
_TIERS = [
    (0,    "🥉 브론즈",     "#cd7f32", "#8b5a2b"),
    (200,  "🥈 실버",       "#eef2f7", "#9aa5b1"),
    (500,  "🥇 골드",       "#ffe066", "#f59e0b"),
    (1000, "💎 플래티넘",   "#d9f7ff", "#22a6c9"),
    (2000, "👑 다이아몬드", "#f3e8ff", "#a855f7"),
]


def _tier_info(score: int):
    idx = 0
    for i, (threshold, *_rest) in enumerate(_TIERS):
        if score >= threshold:
            idx = i
    threshold, label, c1, c2 = _TIERS[idx]
    next_threshold = _TIERS[idx + 1][0] if idx + 1 < len(_TIERS) else None
    return label, c1, c2, threshold, next_threshold


def _render_score_card(score: int) -> None:
    label, c1, c2, cur_th, next_th = _tier_info(score)

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, {c1}, {c2});
            border-radius: 18px; padding: 32px 24px; text-align:center;
            color:#1f2937; box-shadow: 0 10px 28px rgba(0,0,0,.18);
            margin-bottom: 8px;
        ">
            <div style="font-size:13px;letter-spacing:.15em;opacity:.7;text-transform:uppercase;">지식 점수</div>
            <div style="font-size:52px;font-weight:800;margin:6px 0;line-height:1;">{score:,}</div>
            <div style="font-size:22px;font-weight:700;">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if next_th is not None:
        progress = max(0.0, min(1.0, (score - cur_th) / (next_th - cur_th)))
        st.progress(progress, text=f"다음 티어까지 {next_th - score}점 남음")
    else:
        st.progress(1.0, text="🏆 최고 티어 달성!")


def render_stats() -> None:
    st.markdown("# 📊 통계")
    st.caption("Opening Flex에서 직접 연습하고 마스터한 기록만 정리합니다.")

    if not st.session_state.get("user_id"):
        st.warning("먼저 홈 화면에서 닉네임을 입력해주세요.")
        return

    user = get_user_by_id(st.session_state.user_id) or st.session_state.user_data or {}

    with st.spinner("데이터를 불러오는 중..."):
        rows = get_mastery_with_eco(st.session_state.user_id)

    # ── 지식 점수 카드 ───────────────────────────────────────────────────────
    _render_score_card(user.get("total_knowledge_score", 0))
    st.divider()

    if rows is None:
        st.error("DB 연결에 실패했습니다.")
        return
    if not rows:
        st.info("아직 분석된 오프닝이 없습니다. **오프닝연습** 탭에서 게임을 분석해보세요.")
        return

    mastered_rows   = [r for r in rows if r.get("is_mastered")]
    practicing_rows = [r for r in rows if not r.get("is_mastered") and r.get("defense_streak", 0) > 0]
    not_started     = len(rows) - len(mastered_rows) - len(practicing_rows)

    c1, c2, c3 = st.columns(3)
    c1.metric("✅ 마스터한 오프닝", len(mastered_rows))
    c2.metric("📖 연습 중인 오프닝", len(practicing_rows))
    c3.metric("⏳ 아직 시작 안 함", not_started)

    st.divider()

    # ── 마스터한 오프닝 ──────────────────────────────────────────────────────
    st.markdown("### ✅ 마스터한 오프닝")
    if mastered_rows:
        df = pd.DataFrame([
            {
                "오프닝": (r.get("eco_reference") or {}).get("name") or r.get("eco_code", ""),
                "ECO": r.get("eco_code", ""),
                "방어 연속": "🟦🟦🟦 3/3",
            }
            for r in mastered_rows
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("아직 마스터한 오프닝이 없습니다. **오프닝연습**에서 훈련을 시작해보세요!")

    # ── 연습 중인 오프닝 ─────────────────────────────────────────────────────
    st.markdown("### 📖 연습 중인 오프닝")
    if practicing_rows:
        df = pd.DataFrame([
            {
                "오프닝": (r.get("eco_reference") or {}).get("name") or r.get("eco_code", ""),
                "ECO": r.get("eco_code", ""),
                "방어 연속": "🟦" * r.get("defense_streak", 0) + "⬜" * (3 - r.get("defense_streak", 0))
                            + f"  {r.get('defense_streak', 0)}/3",
            }
            for r in sorted(practicing_rows, key=lambda r: r.get("defense_streak", 0), reverse=True)
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("현재 연습 중인 오프닝이 없습니다.")
