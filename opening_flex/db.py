import uuid
import streamlit as st
from supabase import create_client, Client
from typing import Optional


@st.cache_resource
def _get_client() -> Client:
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["key"],
    )


def get_user(platform_type: str, chess_platform_id: str) -> Optional[dict]:
    """닉네임으로 users 테이블 조회. 미존재 또는 오류 시 None 반환."""
    try:
        res = (
            _get_client()
            .table("users")
            .select("*")
            .eq("platform_type", platform_type)
            .eq("chess_platform_id", chess_platform_id)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception:
        return None


def get_user_by_id(user_id: str) -> Optional[dict]:
    """user_id로 users 테이블 재조회 (지식 점수 등 최신 값 갱신용)."""
    try:
        res = (
            _get_client()
            .table("users")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception:
        return None


def create_user(platform_type: str, chess_platform_id: str) -> Optional[dict]:
    """신규 사용자를 users 테이블에 INSERT하고 생성된 row 반환."""
    try:
        res = (
            _get_client()
            .table("users")
            .insert({
                "user_id": str(uuid.uuid4()),
                "platform_type": platform_type,
                "chess_platform_id": chess_platform_id,
                "tier": "FREE",
                "total_knowledge_score": 0,
            })
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception:
        return None


def seed_opening_mastery(user_id: str) -> bool:
    """신규 사용자에게 메이저 오프닝 약점 3개 시딩 (C60, C50, A40)."""
    rows = [
        {"user_id": user_id, "eco_code": "C60", "loss_count": 3, "defense_streak": 0, "is_mastered": False,
         "last_lost_sequence": "1. e4 e5 2. Nf3 Nc6 3. Bb5"},
        {"user_id": user_id, "eco_code": "C50", "loss_count": 2, "defense_streak": 0, "is_mastered": False,
         "last_lost_sequence": "1. e4 e5 2. Nf3 Nc6 3. Bc4"},
        {"user_id": user_id, "eco_code": "A40", "loss_count": 1, "defense_streak": 0, "is_mastered": False,
         "last_lost_sequence": "1. d4 d5"},
    ]
    try:
        _get_client().table("opening_mastery").insert(rows).execute()
        return True
    except Exception:
        return False


def upsert_openings(user_id: str, openings: list[dict]) -> bool:
    """analyze_early_losses 결과를 eco_reference + opening_mastery에 upsert.

    - eco_reference: 새 ECO 코드를 추가하거나 이름을 갱신
    - opening_mastery: loss_count / last_lost_sequence 갱신,
                       기존 defense_streak / is_mastered는 보존
    """
    if not openings:
        return True
    try:
        client = _get_client()

        # 1. eco_reference upsert (신규 오프닝 코드 자동 등록)
        client.table("eco_reference").upsert(
            [{"eco_code": o["eco_code"], "name": o["name"], "family": o["family"]}
             for o in openings],
            on_conflict="eco_code",
        ).execute()

        # 2. 기존 mastery에서 defense_streak / is_mastered 읽어서 보존
        existing = {
            r["eco_code"]: r
            for r in (
                client.table("opening_mastery")
                .select("eco_code,defense_streak,is_mastered")
                .eq("user_id", user_id)
                .execute()
                .data or []
            )
        }

        # 3. opening_mastery upsert
        client.table("opening_mastery").upsert(
            [
                {
                    "user_id": user_id,
                    "eco_code": o["eco_code"],
                    "loss_count": o["loss_count"],
                    "last_lost_sequence": o.get("last_lost_sequence", ""),
                    "opponent_username": o.get("opponent_username") or "",
                    "full_lost_pgn": o.get("full_lost_pgn") or "",
                    "defense_streak": existing.get(o["eco_code"], {}).get("defense_streak", 0),
                    "is_mastered": existing.get(o["eco_code"], {}).get("is_mastered", False),
                }
                for o in openings
            ],
            on_conflict="user_id,eco_code",
        ).execute()

        return True
    except Exception:
        return False


def get_opening_detail(user_id: str, eco_code: str) -> Optional[dict]:
    """특정 eco_code의 mastery + eco_reference 데이터를 반환."""
    try:
        client = _get_client()
        mastery = (
            client.table("opening_mastery")
            .select("*")
            .eq("user_id", user_id)
            .eq("eco_code", eco_code)
            .execute()
        )
        eco = (
            client.table("eco_reference")
            .select("*")
            .eq("eco_code", eco_code)
            .execute()
        )
        if not mastery.data:
            return None
        row = mastery.data[0]
        row["eco_reference"] = eco.data[0] if eco.data else {}
        return row
    except Exception:
        return None


def get_mastery_with_eco(user_id: str) -> Optional[list[dict]]:
    """opening_mastery + eco_reference를 병합하여 반환.
    DB 오류 시 None, 데이터 없음 시 [] 반환."""
    try:
        client = _get_client()

        mastery_res = (
            client.table("opening_mastery")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        rows: list[dict] = mastery_res.data or []

        if not rows:
            return []

        eco_res = client.table("eco_reference").select("*").execute()
        eco_map: dict[str, dict] = {
            e["eco_code"]: e for e in (eco_res.data or [])
        }

        for row in rows:
            row["eco_reference"] = eco_map.get(row.get("eco_code", ""), {})

        return rows
    except Exception:
        return None
