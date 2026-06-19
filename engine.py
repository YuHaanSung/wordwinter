"""
Stockfish HTTP 브릿지 + 방어 기록 엔드포인트.
- GET /move      : Stockfish 최선의 수 + 평가
- GET /topmoves  : 후보 수 N개 (정석/공격적 대안 힌트용)
- GET /eval      : 평가만 (최선의 수 탐색 없이, 블런더 지점 스캔용 — 더 빠름)
- GET /record    : 방어 연속 기록 업데이트
"""

import json
import shutil
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from stockfish import Stockfish

_port:         int | None = None
_sf:           Stockfish | None = None
_sf_path:      str | None = None
_supabase_url: str | None = None
_supabase_key: str | None = None
_lock       = threading.Lock()
_start_lock = threading.Lock()


def init(supabase_url: str, supabase_key: str) -> None:
    """Supabase 자격증명 초기화 — render_training() 최초 호출 때 한 번만 실행."""
    global _supabase_url, _supabase_key
    _supabase_url = supabase_url
    _supabase_key = supabase_key


def _find_binary() -> str | None:
    return shutil.which("stockfish")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _ensure_sf() -> Stockfish:
    global _sf
    if _sf is None:
        _sf = Stockfish(_sf_path)
        # 라이브러리 기본값(turn_perspective=True)은 "차례인 쪽 기준" cp를 반환한다.
        # 항상 "백 기준" 절대값으로 받아야 클라이언트의 부호 처리와 일치한다.
        _sf.set_turn_perspective(False)
    return _sf


def _search(fen: str, depth: int, skill: int) -> dict:
    with _lock:
        sf = _ensure_sf()
        try:
            sf.set_skill_level(skill)
            sf.set_depth(depth)
            sf.set_fen_position(fen)
            move = sf.get_best_move()
            sf.set_fen_position(fen)
            ev = sf.get_evaluation()
            return {"move": move, "eval": ev}
        except Exception:
            global _sf
            _sf = None
            raise


def _top_moves(fen: str, depth: int, skill: int, n: int) -> dict:
    with _lock:
        sf = _ensure_sf()
        try:
            sf.set_skill_level(skill)
            sf.set_depth(depth)
            sf.set_fen_position(fen)
            moves = sf.get_top_moves(n)
            return {"moves": moves}
        except Exception:
            global _sf
            _sf = None
            raise


def _eval_only(fen: str, depth: int, skill: int) -> dict:
    """get_best_move() 탐색을 건너뛰고 평가만 — 블런더 지점 스캔처럼 여러 포지션을
    연달아 평가할 때 _search()보다 약 2배 빠르다."""
    with _lock:
        sf = _ensure_sf()
        try:
            sf.set_skill_level(skill)
            sf.set_depth(depth)
            sf.set_fen_position(fen)
            ev = sf.get_evaluation()
            return {"eval": ev}
        except Exception:
            global _sf
            _sf = None
            raise


def _record(user_id: str, eco_code: str) -> dict:
    """방어 연속 +1. streak >= 3 이면 is_mastered = True."""
    if not _supabase_url or not _supabase_key:
        return {"error": "no credentials", "streak": 0, "mastered": False}
    try:
        from supabase import create_client
        client = create_client(_supabase_url, _supabase_key)
        row = (
            client.table("opening_mastery")
            .select("defense_streak")
            .eq("user_id", user_id)
            .eq("eco_code", eco_code)
            .execute()
        )
        if not row.data:
            return {"error": "not found", "streak": 0, "mastered": False}
        new_streak = min(row.data[0]["defense_streak"] + 1, 3)
        payload: dict = {"defense_streak": new_streak}
        if new_streak >= 3:
            payload["is_mastered"] = True
        client.table("opening_mastery").update(payload) \
              .eq("user_id", user_id).eq("eco_code", eco_code).execute()

        # 지식 점수 적립 (방어 성공 +10, 마스터 +50)
        points = 50 if new_streak >= 3 else 10
        user_row = client.table("users").select("total_knowledge_score") \
                          .eq("user_id", user_id).execute()
        if user_row.data:
            new_score = (user_row.data[0].get("total_knowledge_score") or 0) + points
            client.table("users").update({"total_knowledge_score": new_score}) \
                  .eq("user_id", user_id).execute()

        return {"streak": new_streak, "mastered": new_streak >= 3}
    except Exception as e:
        return {"error": str(e), "streak": 0, "mastered": False}


def _cors(handler: "BaseHTTPRequestHandler") -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        p  = urlparse(self.path)
        qs = parse_qs(p.query)

        if p.path == "/move":
            fen   = qs.get("fen",   [""])[0]
            depth = min(int(qs.get("depth", ["10"])[0]), 20)
            skill = min(int(qs.get("skill", ["20"])[0]), 20)
            if not fen:
                self.send_response(400); self.end_headers(); return
            try:
                result = _search(fen, depth, skill)
                body   = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); _cors(self); self.end_headers()
                self.wfile.write(str(e).encode())

        elif p.path == "/topmoves":
            fen   = qs.get("fen",   [""])[0]
            depth = min(int(qs.get("depth", ["12"])[0]), 20)
            skill = min(int(qs.get("skill", ["20"])[0]), 20)
            n     = min(int(qs.get("n",     ["4"])[0]), 8)
            if not fen:
                self.send_response(400); self.end_headers(); return
            try:
                result = _top_moves(fen, depth, skill, n)
                body   = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); _cors(self); self.end_headers()
                self.wfile.write(str(e).encode())

        elif p.path == "/eval":
            fen   = qs.get("fen",   [""])[0]
            depth = min(int(qs.get("depth", ["6"])[0]), 20)
            skill = min(int(qs.get("skill", ["10"])[0]), 20)
            if not fen:
                self.send_response(400); self.end_headers(); return
            try:
                result = _eval_only(fen, depth, skill)
                body   = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                _cors(self)
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); _cors(self); self.end_headers()
                self.wfile.write(str(e).encode())

        elif p.path == "/record":
            user_id  = qs.get("user_id",  [""])[0]
            eco_code = qs.get("eco_code", [""])[0]
            if not user_id or not eco_code:
                self.send_response(400); self.end_headers(); return
            result = _record(user_id, eco_code)
            body   = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            _cors(self)
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404); self.end_headers()

    def log_message(self, *args):
        pass


def get_port() -> int | None:
    """서버 포트 반환. 최초 호출 시 HTTP 서버를 시작한다."""
    global _port, _sf_path

    with _start_lock:
        if _port is not None:
            return _port
        path = _find_binary()
        if not path:
            return None
        _sf_path = path
        port = _free_port()
        server = HTTPServer(("127.0.0.1", port), _Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        _port = port
        return port
