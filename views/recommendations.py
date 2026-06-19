import streamlit as st

_SITES = [
    {
        "category": "🧠 오프닝 학습",
        "items": [
            ("Chess.com Openings", "https://www.chess.com/openings", "오프닝별 통계·승률·핵심 라인을 데이터로 확인할 수 있는 가장 표준적인 오프닝 백과."),
            ("Lichess Opening Explorer", "https://lichess.org/analysis", "분석판에서 바로 마스터 게임 DB 기반 오프닝 통계를 볼 수 있음. 완전 무료, 가입 불필요."),
            ("Chessable", "https://www.chessable.com", "스페이스드 리피티션(망각곡선) 기반으로 오프닝 라인을 외우는 데 특화된 학습 플랫폼."),
        ],
    },
    {
        "category": "⚔️ 전술·실전 연습",
        "items": [
            ("Chess.com Puzzles", "https://www.chess.com/puzzles", "매일 새로운 전술 퍼즐, 레이팅 기반 난이도 자동 조절."),
            ("Lichess Puzzles", "https://lichess.org/training", "무제한 무료 전술 트레이닝. 테마별(포크, 핀, 희생 등) 필터 가능."),
            ("ChessTempo", "https://chesstempo.com", "전술뿐 아니라 엔드게임·포지션 평가 트레이닝까지 폭넓게 지원."),
        ],
    },
    {
        "category": "🔍 분석 도구",
        "items": [
            ("Lichess 분석판", "https://lichess.org/analysis", "Stockfish 기반 무료 분석. 본인 게임을 붙여넣어 어디서 틀렸는지 바로 확인."),
            ("Chess.com 게임 리뷰", "https://www.chess.com/analysis", "게임 리뷰 + 정확도 점수 + 단계별 추천 수까지 제공."),
        ],
    },
    {
        "category": "📚 커뮤니티 · 강의",
        "items": [
            ("Lichess Study", "https://lichess.org/study", "무료로 나만의 오프닝 스터디를 만들고 공유할 수 있는 기능."),
            ("Chess.com Lessons", "https://www.chess.com/lessons", "초중급자를 위한 단계별 커리큘럼 강의."),
        ],
    },
]


def render_recommendations() -> None:
    st.markdown("# 🔗 사이트 추천")
    st.caption(
        "Opening Flex로 약점 오프닝을 찾고 훈련했다면, 아래 사이트들로 더 깊게 파고들어보세요. "
        "전부 무료로 시작할 수 있는 곳들만 골랐습니다."
    )
    st.divider()

    for group in _SITES:
        st.markdown(f"### {group['category']}")
        for name, url, desc in group["items"]:
            with st.container(border=True):
                st.markdown(f"**[{name}]({url})**")
                st.caption(desc)
        st.write("")
