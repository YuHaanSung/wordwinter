"""
Chess.com 게임 기록에서 '이른 수 안에 패배한 오프닝'을 집계하는 분석 모듈.

흐름:
  1. /games/archives  → 월별 아카이브 URL 목록 조회
  2. 최근 max_months개월 URL → 게임 JSON 다운로드
  3. 각 게임 PGN 파싱:
       - [White] / [Black] / [Result] 헤더로 사용자 패배 여부 판단
       - [ECO] / [ECOUrl] 헤더로 오프닝 코드·이름 추출
       - 본문 수 번호 파싱으로 게임 종료 수 계산
  4. move_threshold 수 이내 종료된 패배 게임만 집계
  5. ECO 코드별 loss_count 내림차순 반환
"""

import re
import requests
from collections import defaultdict

_HEADERS = {"User-Agent": "OpeningFlex/1.0 (educational project)"}

_ECO_FAMILIES: dict[str, str] = {
    "A": "Flank / Queen's Pawn Opening",
    "B": "Semi-Open Game",
    "C": "King's Pawn Opening",
    "D": "Queen's Pawn Game",
    "E": "Indian Defense",
}


# ── PGN 파싱 헬퍼 ──────────────────────────────────────────────────────────────

def _parse_headers(pgn: str) -> dict[str, str]:
    """PGN 헤더 섹션에서 key-value 딕셔너리 추출."""
    return {
        m.group(1): m.group(2)
        for m in re.finditer(r'\[(\w+)\s+"([^"]+)"\]', pgn)
    }


def _count_moves(pgn: str) -> int:
    """PGN 본문에서 마지막 수 번호를 반환 (전체 게임 길이).

    Chess.com PGN 형식 예시:
      1. e4 {[%clk 0:10:00]} 1... e5 {[%clk 0:09:55]} 2. Nf3 ...
    """
    # 헤더(]로 끝나는 줄들)와 본문을 분리
    parts = pgn.split("\n\n", 1)
    if len(parts) < 2:
        return 0
    body = parts[1]
    # 중괄호 주석 제거 → {[%clk ...]} {[%eval ...]} 등
    body = re.sub(r"\{[^}]*\}", "", body)
    # "N." 또는 "N..." 패턴에서 숫자 추출
    nums = re.findall(r"\b(\d+)\.\.?\.?", body)
    return max((int(n) for n in nums), default=0)


def _extract_sequence(pgn: str, up_to_move: int = 8) -> str:
    """PGN 본문에서 처음 up_to_move 수까지 기보를 깔끔하게 추출.

    반환 예: "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6"
    """
    parts = pgn.split("\n\n", 1)
    if len(parts) < 2:
        return ""
    body = parts[1]
    body = re.sub(r"\{[^}]*\}", "", body)   # 주석 제거
    body = re.sub(r"\$\d+", "", body)        # NAG 심볼 제거
    body = re.sub(r"\s+", " ", body).strip()

    result: list[str] = []
    for token in body.split():
        if token in {"1-0", "0-1", "1/2-1/2", "*"}:
            break
        m = re.match(r"^(\d+)\.", token)
        if m and int(m.group(1)) > up_to_move:
            break
        # "N..." (흑 수 표기) 은 건너뜀 — "N." 만 표시
        if re.match(r"^\d+\.\.\.", token):
            continue
        result.append(token)
    return " ".join(result)


def _eco_name_from_url(eco_url: str) -> str:
    """ECOUrl 슬러그에서 오프닝 이름 추출.
    예: .../Italian-Game-Giuoco-Piano → 'Italian Game Giuoco Piano'
    """
    if not eco_url:
        return ""
    slug = eco_url.rstrip("/").split("/")[-1]
    return slug.replace("-", " ").title()


# ── 게임 다운로드 ──────────────────────────────────────────────────────────────

def _fetch_recent_games(username: str, max_months: int = 2) -> list[dict]:
    """최근 max_months개월의 Chess.com 게임 목록을 반환."""
    try:
        res = requests.get(
            f"https://api.chess.com/pub/player/{username.lower()}/games/archives",
            headers=_HEADERS,
            timeout=8,
        )
        if res.status_code != 200:
            return []
        archives: list[str] = res.json().get("archives", [])
    except Exception:
        return []

    games: list[dict] = []
    for url in reversed(archives[-max_months:]):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=12)
            if r.status_code == 200:
                games.extend(r.json().get("games", []))
        except Exception:
            continue
    return games


# ── 메인 분석 함수 ─────────────────────────────────────────────────────────────

def analyze_games(username: str, games: list[dict], move_threshold: int = 20) -> list[dict]:
    """이미 가져온 games 리스트에서 move_threshold 수 이내에 패배한 오프닝을 집계.

    Args:
        username:       Chess.com 닉네임 (백/흑 판별용)
        games:          _fetch_recent_games() 로 가져온 게임 목록
        move_threshold: 이 수 이하로 끝난 게임만 '오프닝 패배'로 집계

    Returns:
        loss_count 내림차순으로 정렬된 dict 리스트.
        각 항목: {eco_code, name, family, loss_count, last_lost_sequence}
    """
    user_lower = username.lower()

    stats: dict[str, dict] = defaultdict(lambda: {
        "name": "",
        "family": "",
        "loss_count": 0,
        "last_lost_sequence": "",
        "opponent_username": "",
        "full_lost_pgn": "",
    })

    for game in games:
        pgn = game.get("pgn", "")
        if not pgn:
            continue

        h = _parse_headers(pgn)

        # ── 패배 여부 판단 ─────────────────────────────────────────────────
        white = h.get("White", "").lower()
        black = h.get("Black", "").lower()
        result = h.get("Result", "")

        user_lost = (
            (user_lower == white and result == "0-1") or
            (user_lower == black and result == "1-0")
        )
        if not user_lost:
            continue

        # ── 게임 길이 필터 ─────────────────────────────────────────────────
        move_count = _count_moves(pgn)
        if move_count == 0 or move_count > move_threshold:
            continue

        # ── ECO 정보 추출 ──────────────────────────────────────────────────
        eco_code = h.get("ECO", "").strip()
        if not eco_code:
            continue

        eco_url = h.get("ECOUrl", "")
        name = _eco_name_from_url(eco_url) or eco_code
        family = _ECO_FAMILIES.get(eco_code[0].upper(), "Other")

        s = stats[eco_code]
        s["name"] = name
        s["family"] = family
        s["loss_count"] += 1
        if not s["last_lost_sequence"]:
            s["last_lost_sequence"] = _extract_sequence(pgn, up_to_move=8)
            # 리벤지 봇용: 상대 닉네임 + 게임 전체 수순 보관
            # full_lost_pgn 맨 앞에 "W|"/"B|" 로 유저가 그 게임에서 둔 색을 표시해둔다.
            # (ply 인덱스의 짝/홀만으로는 어느 색이 '유저'인지 알 수 없어서 색 정보를 같이 묻어둠)
            s["opponent_username"] = h.get("Black") if user_lower == white else h.get("White")
            user_color_code = "W" if user_lower == white else "B"
            s["full_lost_pgn"] = user_color_code + "|" + _extract_sequence(pgn, up_to_move=300)

    return sorted(
        [{"eco_code": k, **v} for k, v in stats.items()],
        key=lambda x: x["loss_count"],
        reverse=True,
    )


def analyze_early_losses(
    username: str,
    move_threshold: int = 20,
    max_months: int = 2,
) -> list[dict]:
    """username의 최근 게임을 가져와 analyze_games()로 집계 (편의 함수)."""
    games = _fetch_recent_games(username, max_months)
    return analyze_games(username, games, move_threshold)
