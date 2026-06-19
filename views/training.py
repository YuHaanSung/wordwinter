import base64
import json
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from db import get_opening_detail

# ── 커스텀 기물 이미지 ────────────────────────────────────────────────────────
_PIECES_DIR = Path(__file__).parent.parent / "static" / "pieces"

_PIECE_FILES = {
    "wR": "white_rook.png",  "bR": "black_rook.png",
    "wQ": "white_queen.png", "bQ": "black_queen.png",
    "wP": "white_pawn.png",  "bP": "black_pawn.png",
    "wN": "white_knight.png","bN": "black_knight.png",
    "wK": "white_king.png",  "bK": "black_king.png",
    "wB": "white_bishop.png","bB": "black_bishop.png",
}

_DIFFICULTY_MAP = {
    "쉬움":   (5,  10),   # (skill_level, depth)
    "보통":   (10, 12),
    "어려움": (15, 15),
    "최강":   (20, 18),
}

# 시딩 데이터처럼 last_lost_sequence가 비어있을 때 쓸 기본 시퀀스
_DEFAULT_SEQUENCES = {
    "C60": "1. e4 e5 2. Nf3 Nc6 3. Bb5",
    "C50": "1. e4 e5 2. Nf3 Nc6 3. Bc4",
    "A40": "1. d4 d5",
}


def _load_piece_uris() -> dict:
    uris = {}
    for code, filename in _PIECE_FILES.items():
        path = _PIECES_DIR / filename
        if path.exists():
            data = base64.b64encode(path.read_bytes()).decode()
            uris[code] = f"data:image/png;base64,{data}"
    return uris


# ── HTML 템플릿 ────────────────────────────────────────────────────────────────
# __OPENING_MOVES__ : JSON 문자열로 치환
# __PIECE_URIS__    : JSON 객체로 치환 (base64 data URI 맵)
# __SKILL_LEVEL__   : Stockfish UCI Skill Level (0-20)
# __DEPTH__         : go depth 값

_BOARD_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet"
  href="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.css">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: transparent;
  padding: 8px 4px;
}
.layout { display: flex; gap: 10px; align-items: flex-start; }

/* 세로 평가 바 */
.eval-wrap {
  width: 16px; flex-shrink: 0; align-self: stretch;
  background: #334155; border-radius: 4px; overflow: hidden;
  position: relative;
}
.eval-black { position: absolute; top: 0; width: 100%; background: #1e293b; transition: height .5s ease; }
.eval-white { position: absolute; bottom: 0; width: 100%; background: #f1f5f9; transition: height .5s ease; }

#board  { width: 360px; flex-shrink: 0; }
.side { flex: 1; display: flex; flex-direction: column; gap: 9px; min-width: 155px; }

.status-card {
  background: #1e293b; color: #f8fafc;
  border-radius: 10px; padding: 10px 14px;
}
.lbl { font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing:.05em; }
.status-val { font-size: 15px; font-weight: 700; margin-top: 3px; }
.status-val.check { color: #f87171; }
.status-val.over  { color: #4ade80; }
.score-row { font-size: 11px; color: #94a3b8; margin-top: 4px; }
#revenge-label { font-size: 11px; color: #fca5a5; margin-top: 4px; font-weight: 700; }
#hint-legend { font-size: 11px; color: #64748b; text-align: center; }

.eval-card {
  background: #0f172a; color: #f8fafc;
  border-radius: 10px; padding: 8px 14px;
  display: flex; align-items: center; justify-content: space-between;
}
.eval-num { font-size: 15px; font-weight: 700; }
.eval-num.adv  { color: #4ade80; }
.eval-num.disadv { color: #f87171; }
.eval-num.even { color: #94a3b8; }
#sf-badge {
  font-size: 10px; padding: 2px 7px; border-radius: 99px;
  background: #1e293b; color: #64748b;
}
#sf-badge.ready { background: #14532d; color: #4ade80; }

.moves-card {
  background: #fff; border: 1px solid #e2e8f0;
  border-radius: 10px; padding: 10px 12px;
}
.moves-body {
  font-size: 12px; color: #475569; line-height: 1.9;
  height: 88px; overflow-y: auto; margin-top: 5px;
}

#result-banner {
  display: none;
  padding: 10px 14px; border-radius: 10px;
  font-size: 13px; font-weight: 700; text-align: center;
}
#result-banner.pass { background: #dcfce7; color: #166534; }
#result-banner.fail { background: #fee2e2; color: #991b1b; }

.btn-row { display: flex; gap: 5px; flex-wrap: wrap; }
button {
  padding: 7px 10px; border: none; border-radius: 8px;
  font-size: 12px; font-weight: 600; cursor: pointer; transition: opacity .15s;
}
button:hover { opacity: .82; }
.btn-p    { background: #3b82f6; color: #fff; }
.btn-s    { background: #f1f5f9; color: #334155; border: 1px solid #e2e8f0; }
.btn-hint { background: #f59e0b; color: #fff; }
</style>
</head>
<body>
<div class="layout">
  <!-- 세로 평가 바 -->
  <div class="eval-wrap" id="eval-bar" style="height:360px">
    <div class="eval-black" id="eval-black" style="height:50%"></div>
    <div class="eval-white" id="eval-white" style="height:50%"></div>
  </div>

  <div id="board"></div>

  <div class="side">
    <div class="status-card">
      <div class="lbl">게임 상태</div>
      <div class="status-val" id="sv">백 차례</div>
      <div class="score-row" id="score-row"></div>
      <div id="revenge-label" style="display:none"></div>
    </div>

    <!-- 평가 수치 + 엔진 상태 -->
    <div class="eval-card">
      <div>
        <div class="lbl">엔진 평가</div>
        <div class="eval-num even" id="eval-num">±0.0</div>
      </div>
      <span id="sf-badge">⏳ 로딩</span>
    </div>

    <div class="moves-card">
      <div class="lbl">기보</div>
      <div class="moves-body" id="mv">
        <span style="color:#cbd5e1">수를 두면 기록됩니다</span>
      </div>
    </div>

    <div id="result-banner"></div>
    <div id="hint-legend" style="display:none"></div>

    <div class="btn-row">
      <button class="btn-p" onclick="resetBoard()">↺ 처음으로</button>
      <button class="btn-s" onclick="undoMove()">← 무르기</button>
      <button class="btn-s" onclick="flipBoard()">⇅ 뒤집기</button>
      <button class="btn-hint" onclick="requestHint()">💡 힌트</button>
    </div>
  </div>
</div>

<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>
<script>
var OPENING_MOVES = __OPENING_MOVES__;
var PIECE_URIS    = __PIECE_URIS__;
var DEPTH         = __DEPTH__;
var SKILL_LEVEL   = __SKILL_LEVEL__;
var SF_PORT       = __SF_PORT__;
var USER_ID       = __USER_ID__;
var ECO_CODE      = __ECO_CODE__;
var SUPABASE_URL  = __SUPABASE_URL__;
var SUPABASE_KEY  = __SUPABASE_KEY__;
var REVENGE_PGN        = __REVENGE_PGN__;        /* 항상 채워짐: 전체 패배 기보(있으면) */
var OPPONENT_NAME      = __OPPONENT_NAME__;
var REVENGE_REPLAY_ON  = __REVENGE_REPLAY_ON__;   /* 체크박스로 "재현" 자체를 켰을 때만 true */

var game, board;
var openingPlyCount = 0;
var testResult      = null;
var userColor       = null;
var pendingBot      = false;
var hintMode        = false;
var hintArrows      = [];   /* 여러 색 화살표 (정석/공격적 대안) */
var reqId           = 0;   /* 오래된 HTTP 응답 무시용 */
var lastEvalCp      = 0;   /* 마지막 엔진 평가 (사용자 기준 cp) */

/* ── 리벤지 데이터: 전체 패배 기보 파싱 (블런더 지점 스캔 + 리벤지 재현 양쪽에 사용) ── */
var hasFullHistory  = !!(REVENGE_PGN && REVENGE_PGN.trim());
var revengeTokens   = [];
var userHistColor   = null;   /* 'w' | 'b' — 실제 패배한 게임에서 유저가 둔 색 */
var revengeOn       = false;  /* 상대 수를 실제로 "재현"할지 — 데이터 존재 + 체크박스 둘 다 필요 */
var revengeDerailed = false;

function parseRevengeTokens(pgnText) {
  var out = [];
  var tokens = pgnText.trim().split(/\s+/);
  for (var i = 0; i < tokens.length; i++) {
    if (/^\d+\./.test(tokens[i])) continue;
    out.push(tokens[i]);
  }
  return out;
}

if (hasFullHistory) {
  var rawRevenge = REVENGE_PGN.trim();
  /* "W|1. e4 e5 ..." 형식: 맨 앞 글자가 유저가 그 게임에서 둔 색 */
  if (rawRevenge.length > 1 && rawRevenge[1] === '|' && (rawRevenge[0] === 'W' || rawRevenge[0] === 'B')) {
    userHistColor = rawRevenge[0] === 'W' ? 'w' : 'b';
    revengeTokens = parseRevengeTokens(rawRevenge.slice(2));
  } else {
    revengeTokens = parseRevengeTokens(rawRevenge);   /* 구버전 포맷 호환 */
  }
  revengeOn = REVENGE_REPLAY_ON && revengeTokens.length > 0;
}

/* 사용자가 과거와 똑같이 두고 있는 동안에만 상대의 실제 수를 그대로 재현.
   한번이라도 다르게 두면(=과거보다 잘 두려는 시도) 그 즉시 일반 엔진으로 전환. */
function tryRevengeMove() {
  if (!revengeOn || revengeDerailed) return false;
  var hist = game.history();
  if (hist.length >= revengeTokens.length) return false;
  for (var i = 0; i < hist.length; i++) {
    if (hist[i] !== revengeTokens[i]) { revengeDerailed = true; updateRevengeLabel(); return false; }
  }
  var mv = game.move(revengeTokens[hist.length], { sloppy: true });
  if (!mv) { revengeDerailed = true; updateRevengeLabel(); return false; }
  board.position(game.fen());
  updateStatus();
  setBadge('🗡️ 리벤지 봇 (' + (OPPONENT_NAME || '상대') + ')', true);
  _refreshRevengeEval();
  return true;
}

/* 리벤지 모드는 실제 엔진 탐색 없이 기록을 재현하므로 lastEvalCp가 갱신되지 않은 채
   남을 수 있다 (예: 7수 내내 과거와 동일하게 두면 평가가 초기값 0에 머물러 판정이 틀어짐).
   매 리벤지 수 이후 평가만 별도로 새로 받아온 다음 판정한다. */
function _refreshRevengeEval() {
  if (game.game_over()) { checkTest(); return; }
  if (SF_PORT) {
    fetch(sfUrl(game.fen()))
      .then(function(r) { return r.json(); })
      .then(function(data) { if (data.eval) updateEvalFromSF(data.eval); checkTest(); })
      .catch(function() { checkTest(); });
  } else {
    var cp = staticEval(game);
    lastEvalCp = userColor === 'b' ? -cp : cp;
    updateEval(lastEvalCp);
    checkTest();
  }
}

/* ── JS 체스 엔진 (알파-베타 + 기물 위치 테이블) ──────────────────── */
var MV = { p:100, n:320, b:330, r:500, q:900, k:20000 };

/* 기물 위치 점수 테이블 (백 기준, rank8=row0) */
var PST = {
  p:[[  0,  0,  0,  0,  0,  0,  0,  0],
     [ 50, 50, 50, 50, 50, 50, 50, 50],
     [ 10, 10, 20, 30, 30, 20, 10, 10],
     [  5,  5, 10, 25, 25, 10,  5,  5],
     [  0,  0,  0, 20, 20,  0,  0,  0],
     [  5, -5,-10,  0,  0,-10, -5,  5],
     [  5, 10, 10,-20,-20, 10, 10,  5],
     [  0,  0,  0,  0,  0,  0,  0,  0]],
  n:[[-50,-40,-30,-30,-30,-30,-40,-50],
     [-40,-20,  0,  0,  0,  0,-20,-40],
     [-30,  0, 10, 15, 15, 10,  0,-30],
     [-30,  5, 15, 20, 20, 15,  5,-30],
     [-30,  0, 15, 20, 20, 15,  0,-30],
     [-30,  5, 10, 15, 15, 10,  5,-30],
     [-40,-20,  0,  5,  5,  0,-20,-40],
     [-50,-40,-30,-30,-30,-30,-40,-50]],
  b:[[-20,-10,-10,-10,-10,-10,-10,-20],
     [-10,  0,  0,  0,  0,  0,  0,-10],
     [-10,  0,  5, 10, 10,  5,  0,-10],
     [-10,  5,  5, 10, 10,  5,  5,-10],
     [-10,  0, 10, 10, 10, 10,  0,-10],
     [-10, 10, 10, 10, 10, 10, 10,-10],
     [-10,  5,  0,  0,  0,  0,  5,-10],
     [-20,-10,-10,-10,-10,-10,-10,-20]],
  r:[[  0,  0,  0,  0,  0,  0,  0,  0],
     [  5, 10, 10, 10, 10, 10, 10,  5],
     [ -5,  0,  0,  0,  0,  0,  0, -5],
     [ -5,  0,  0,  0,  0,  0,  0, -5],
     [ -5,  0,  0,  0,  0,  0,  0, -5],
     [ -5,  0,  0,  0,  0,  0,  0, -5],
     [ -5,  0,  0,  0,  0,  0,  0, -5],
     [  0,  0,  0,  5,  5,  0,  0,  0]],
  q:[[-20,-10,-10, -5, -5,-10,-10,-20],
     [-10,  0,  0,  0,  0,  0,  0,-10],
     [-10,  0,  5,  5,  5,  5,  0,-10],
     [ -5,  0,  5,  5,  5,  5,  0, -5],
     [  0,  0,  5,  5,  5,  5,  0, -5],
     [-10,  5,  5,  5,  5,  5,  0,-10],
     [-10,  0,  5,  0,  0,  0,  0,-10],
     [-20,-10,-10, -5, -5,-10,-10,-20]],
  k:[[-30,-40,-40,-50,-50,-40,-40,-30],
     [-30,-40,-40,-50,-50,-40,-40,-30],
     [-30,-40,-40,-50,-50,-40,-40,-30],
     [-30,-40,-40,-50,-50,-40,-40,-30],
     [-20,-30,-30,-40,-40,-30,-30,-20],
     [-10,-20,-20,-20,-20,-20,-20,-10],
     [ 20, 20,  0,  0,  0,  0, 20, 20],
     [ 20, 30, 10,  0,  0, 10, 30, 20]]
};

function pstVal(type, color, sq) {
  var tbl = PST[type]; if (!tbl) return 0;
  var f = sq.charCodeAt(0) - 97;
  var r = parseInt(sq[1]);
  var row = color === 'w' ? 8 - r : r - 1;
  return tbl[row][f];
}

function staticEval(g) {
  if (g.in_checkmate()) return g.turn() === 'w' ? -99999 : 99999;
  if (g.in_draw() || g.in_stalemate()) return 0;
  var score = 0;
  var brd = g.board();
  for (var r = 0; r < 8; r++) {
    for (var f = 0; f < 8; f++) {
      var sq = brd[r][f]; if (!sq) continue;
      var sqName = String.fromCharCode(97 + f) + (8 - r);
      var v = (MV[sq.type] || 0) + pstVal(sq.type, sq.color, sqName);
      if (sq.color === 'w') score += v; else score -= v;
    }
  }
  return score;
}

function alphaBeta(g, depth, alpha, beta, isMax) {
  if (depth === 0 || g.game_over()) return staticEval(g);
  var moves = g.moves({ verbose: true });
  /* 캡처 우선 정렬 → 가지치기 효율 향상 */
  moves.sort(function(a, b) {
    return (b.captured ? MV[b.captured] || 0 : 0) -
           (a.captured ? MV[a.captured] || 0 : 0);
  });
  if (isMax) {
    var best = -Infinity;
    for (var i = 0; i < moves.length; i++) {
      g.move(moves[i]); best = Math.max(best, alphaBeta(g, depth-1, alpha, beta, false)); g.undo();
      alpha = Math.max(alpha, best);
      if (alpha >= beta) break;
    }
    return best;
  } else {
    var best = Infinity;
    for (var i = 0; i < moves.length; i++) {
      g.move(moves[i]); best = Math.min(best, alphaBeta(g, depth-1, alpha, beta, true)); g.undo();
      beta = Math.min(beta, best);
      if (alpha >= beta) break;
    }
    return best;
  }
}

function getBestMove(depth) {
  var moves = game.moves({ verbose: true }); if (!moves.length) return null;
  var isMax = game.turn() === 'w';
  var bestMove = null, bestScore = isMax ? -Infinity : Infinity;
  /* 같은 점수일 때 다양성을 위해 섞기 */
  moves.sort(function() { return Math.random() - 0.5; });
  moves.sort(function(a, b) {
    return (b.captured ? MV[b.captured] || 0 : 0) -
           (a.captured ? MV[a.captured] || 0 : 0);
  });
  for (var i = 0; i < moves.length; i++) {
    game.move(moves[i]);
    var sc = alphaBeta(game, depth - 1, -Infinity, Infinity, !isMax);
    game.undo();
    if (isMax ? sc > bestScore : sc < bestScore) { bestScore = sc; bestMove = moves[i]; }
  }
  return { move: bestMove, score: bestScore };
}

function setBadge(text, ready) {
  var el = document.getElementById('sf-badge');
  el.textContent = text;
  el.className = ready ? 'ready' : '';
}

/* ── Stockfish HTTP / JS 폴백 ──────────────────────────────────────── */
function sfUrl(fen) {
  return 'http://127.0.0.1:' + SF_PORT
    + '/move?fen=' + encodeURIComponent(fen)
    + '&depth=' + DEPTH + '&skill=' + SKILL_LEVEL;
}

function updateEvalFromSF(ev) {
  if (!ev) return;
  var cp = ev.type === 'mate'
    ? (ev.value > 0 ? 9999 : -9999)
    : ev.value;            /* 스톡피쉬는 백 기준 cp 반환 */
  if (userColor === 'b') cp = -cp;
  lastEvalCp = cp;
  updateEval(cp);
}

/* JS 미니맥스 폴백 */
function _jsBotMove() {
  setTimeout(function() {
    var res = getBestMove(DEPTH);
    pendingBot = false;
    setBadge('⚠ JS 폴백', false);
    if (res && res.move) {
      lastEvalCp = userColor === 'b' ? -res.score : res.score;
      updateEval(lastEvalCp);
      applyEngineMove(res.move);
    }
  }, 30);
}

function requestBotMove() {
  if (game.game_over() || pendingBot) return;
  if (tryRevengeMove()) return;   /* 리벤지 모드: 상대 실제 수 재현 성공 시 엔진 호출 건너뜀 */
  pendingBot = true;
  var id = ++reqId;
  setBadge('🤔 생각 중...', true);

  if (!SF_PORT) { _jsBotMove(); return; }

  fetch(sfUrl(game.fen()))
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (reqId !== id) return;          /* 리셋으로 무효화된 응답 무시 */
      pendingBot = false;
      setBadge('🟢 Stockfish 16', true);
      if (data.move) {
        updateEvalFromSF(data.eval);
        applyUciMove(data.move);
      }
    })
    .catch(function() {
      if (reqId !== id) return;
      _jsBotMove();
    });
}

function requestHint() {
  if (game.game_over() || pendingBot || testResult !== null) return;
  if (userColor !== null && game.turn() !== userColor) return;
  removeArrows();
  var id = ++reqId;
  setBadge('🤔 힌트...', true);

  if (!SF_PORT) {
    setTimeout(function() {
      var res = getBestMove(Math.max(DEPTH, 4));
      setBadge('🟢 JS 엔진', true);
      if (res && res.move) showHintArrows([{ Move: res.move.from + res.move.to }]);
    }, 30);
    return;
  }

  /* 힌트는 depth를 최소 12 이상으로, 후보 4개를 받아 정석/공격적 대안으로 분류 */
  var hintUrl = 'http://127.0.0.1:' + SF_PORT
    + '/topmoves?fen=' + encodeURIComponent(game.fen())
    + '&depth=' + Math.max(DEPTH, 12) + '&skill=' + SKILL_LEVEL + '&n=4';

  fetch(hintUrl)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (reqId !== id) return;
      setBadge('🟢 Stockfish 16', true);
      showHintArrows(data.moves || []);
    })
    .catch(function() {
      if (reqId !== id) return;
      var res = getBestMove(Math.max(DEPTH, 4));
      setBadge('⚠ JS 폴백', false);
      if (res && res.move) showHintArrows([{ Move: res.move.from + res.move.to }]);
    });
}

/* 후보 수 목록(엔진 순위) 중 1번 = 정석 추천, 캡처/체크가 되는 첫 수 = 공격적 대안 */
function classifyHintMoves(moves) {
  if (!moves.length) return { normal: null, aggressive: null };
  var normal = moves[0];
  var aggressive = null;
  for (var i = 1; i < moves.length; i++) {
    var uci = moves[i].Move;
    var g2 = new Chess(game.fen());
    var mv = g2.move({ from: uci.slice(0,2), to: uci.slice(2,4), promotion: uci.length>4?uci[4]:'q' });
    if (mv && (mv.captured || g2.in_check())) { aggressive = moves[i]; break; }
  }
  return { normal: normal, aggressive: aggressive };
}

var hintGen = 0;   /* 힌트 연속 클릭 시 이전 타이머가 새 화살표를 조기 삭제하는 것 방지 */

function showHintArrows(moves) {
  var myGen = ++hintGen;
  var cls = classifyHintMoves(moves);
  var legend = document.getElementById('hint-legend');
  var parts = [];
  if (cls.normal) {
    drawArrowColored(cls.normal.Move.slice(0,2), cls.normal.Move.slice(2,4), 'rgba(245,158,11,.85)');
    parts.push('🟠 정석 추천');
  }
  if (cls.aggressive) {
    drawArrowColored(cls.aggressive.Move.slice(0,2), cls.aggressive.Move.slice(2,4), 'rgba(220,38,38,.85)');
    parts.push('🔴 공격적 대안');
  }
  if (parts.length) {
    legend.textContent = parts.join('   ·   ');
    legend.style.display = 'block';
  }
  setTimeout(function() {
    if (hintGen !== myGen) return;   /* 그 사이 새 힌트 요청이 있었으면 건드리지 않음 */
    removeArrows();
  }, 4000);
}

/* ── 힌트 화살표 (여러 색 동시 표시 가능) ──────────────────────────── */
function squareMid(sq) {
  var el = document.querySelector('.square-' + sq);
  if (!el) return null;
  var sr = el.getBoundingClientRect();
  var br = document.getElementById('board').getBoundingClientRect();
  return { x: sr.left - br.left + sr.width/2, y: sr.top - br.top + sr.height/2 };
}

function drawArrowColored(from, to, color) {
  var f = squareMid(from), t = squareMid(to);
  if (!f || !t) return;
  var boardEl = document.getElementById('board');
  var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  var markerId = 'ah-' + hintArrows.length + '-' + Math.floor(Math.random() * 1e6);
  svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:10';
  svg.innerHTML =
    '<defs><marker id="' + markerId + '" markerWidth="4" markerHeight="4" refX="2" refY="2" orient="auto">' +
    '<path d="M0,0 L4,2 L0,4 Z" fill="' + color + '"/></marker></defs>' +
    '<line x1="' + f.x + '" y1="' + f.y + '" x2="' + t.x + '" y2="' + t.y + '"' +
    ' stroke="' + color + '" stroke-width="6" stroke-linecap="round"' +
    ' marker-end="url(#' + markerId + ')"/>';
  boardEl.style.position = 'relative';
  boardEl.appendChild(svg);
  hintArrows.push(svg);
}

function removeArrows() {
  hintArrows.forEach(function(el) { el.remove(); });
  hintArrows = [];
  var legend = document.getElementById('hint-legend');
  if (legend) legend.style.display = 'none';
}

/* ── 평가 표시 ─────────────────────────────────────────────────────── */
function updateEval(cp) {
  /* 바: 0% = 완전 흑 유리, 100% = 완전 백 유리, 50% = 균형 */
  var pct  = 50 + Math.min(Math.max(cp / 10, -45), 45);
  var wPct = pct;
  var bPct = 100 - pct;
  document.getElementById('eval-white').style.height = wPct + '%';
  document.getElementById('eval-black').style.height = bPct + '%';

  var el = document.getElementById('eval-num');
  if (cp >= 9000) {
    el.textContent = '#';
    el.className = 'eval-num adv';
  } else if (cp <= -9000) {
    el.textContent = '-#';
    el.className = 'eval-num disadv';
  } else {
    var v = (cp / 100).toFixed(1);
    el.textContent = cp > 0 ? '+' + v : v;
    el.className = 'eval-num ' + (cp > 20 ? 'adv' : cp < -20 ? 'disadv' : 'even');
  }
}

/* ── 오프닝 수순 재현 ───────────────────────────────────────────────── */
function buildGame() {
  var g = new Chess();
  var count = 0;
  if (OPENING_MOVES) {
    var tokens = OPENING_MOVES.trim().split(/\s+/);
    for (var i = 0; i < tokens.length; i++) {
      if (/^\d+\./.test(tokens[i])) continue;
      if (!g.move(tokens[i], { sloppy: true })) break;
      count++;
    }
  }
  openingPlyCount = count;
  return g;
}

function interactivePlies() {
  return game.history().length - openingPlyCount;
}

/* ── 테스트 판정 → 자동 기록 + 자동 재시작 ────────────────────────── */
function evalText() {
  if (lastEvalCp >= 9000) return '#+';
  if (lastEvalCp <= -9000) return '#-';
  return (lastEvalCp >= 0 ? '+' : '') + (lastEvalCp / 100).toFixed(1);
}

function checkTest() {
  if (testResult !== null) return;
  var uColor = userColor || 'w';
  var passed;

  if (game.in_checkmate()) {
    passed = (game.turn() !== uColor);
  } else if (game.in_stalemate() || game.in_draw()) {
    passed = true;
  } else if (interactivePlies() >= 7) {
    passed = (lastEvalCp >= -100);
  } else {
    return;
  }

  testResult = passed ? 'pass' : 'fail';
  var banner = document.getElementById('result-banner');
  banner.style.display = 'block';
  banner.className = passed ? 'pass' : 'fail';

  if (passed) {
    banner.textContent = '✅ 방어 성공! (' + evalText() + ') — 기록 중...';
    _autoRecord();
  } else {
    banner.textContent = '❌ 방어 실패 (' + evalText() + ') — 3초 후 재시작';
    _autoResetStreak();
    setTimeout(resetBoard, 3000);
  }
}

/* 실패 시 "연속" 기록을 0으로 리셋 (실패해도 안 끊기면 '연속'이 아니므로) */
function _autoResetStreak() {
  if (!USER_ID || !ECO_CODE || !SUPABASE_URL || !SUPABASE_KEY) return;
  var url = SUPABASE_URL + '/rest/v1/opening_mastery'
    + '?user_id=eq.' + encodeURIComponent(USER_ID)
    + '&eco_code=eq.' + encodeURIComponent(ECO_CODE);
  fetch(url, {
    method: 'PATCH',
    headers: Object.assign({ 'Prefer': 'return=minimal' }, _sbHeaders()),
    body: JSON.stringify({ defense_streak: 0 }),
  }).catch(function() {});
}

/* Supabase REST API를 브라우저에서 직접 호출 (anon key는 공개용, 안전) */
function _sbHeaders() {
  return {
    'apikey': SUPABASE_KEY,
    'Authorization': 'Bearer ' + SUPABASE_KEY,
    'Content-Type': 'application/json',
  };
}

function _autoRecord() {
  if (!USER_ID || !ECO_CODE || !SUPABASE_URL || !SUPABASE_KEY) {
    document.getElementById('result-banner').textContent = '✅ 방어 성공! — 3초 후 재시작';
    setTimeout(resetBoard, 3000);
    return;
  }

  var base = SUPABASE_URL + '/rest/v1/opening_mastery'
    + '?user_id=eq.' + encodeURIComponent(USER_ID)
    + '&eco_code=eq.' + encodeURIComponent(ECO_CODE);

  fetch(base + '&select=defense_streak', { headers: _sbHeaders() })
    .then(function(r) { return r.json(); })
    .then(function(rows) {
      if (!rows || !rows.length) throw new Error('not found');
      var newStreak = Math.min(rows[0].defense_streak + 1, 3);
      var mastered  = newStreak >= 3;
      var payload   = { defense_streak: newStreak };
      if (mastered) payload.is_mastered = true;

      return fetch(base, {
        method: 'PATCH',
        headers: Object.assign({ 'Prefer': 'return=minimal' }, _sbHeaders()),
        body: JSON.stringify(payload),
      }).then(function() { return { streak: newStreak, mastered: mastered }; });
    })
    .then(function(res) {
      var banner = document.getElementById('result-banner');
      var pts = res.mastered ? 50 : 10;
      _awardKnowledge(pts);
      if (res.mastered) {
        /* 마스터 달성 — 위쪽 화면(Python)이 곧 감지해서 축하 메시지 + 오프닝연습 탭으로
           이동시키므로 여기서는 보드를 리셋하지 않고 배너만 보여준다 */
        banner.textContent = '🎉 마스터 달성! (3/3) +' + pts + '점 — 잠시 후 오프닝연습 화면으로 이동합니다';
      } else {
        banner.textContent = '✅ 방어 성공! (' + res.streak + '/3) +' + pts + '점 — 3초 후 재시작';
        setTimeout(resetBoard, 3000);
      }
    })
    .catch(function() {
      /* 직접 호출 실패 시 엔진 HTTP 폴백 */
      if (!SF_PORT) {
        document.getElementById('result-banner').textContent = '✅ 방어 성공! — 기록 실패';
        setTimeout(resetBoard, 3000);
        return;
      }
      var url = 'http://127.0.0.1:' + SF_PORT
        + '/record?user_id=' + encodeURIComponent(USER_ID)
        + '&eco_code=' + encodeURIComponent(ECO_CODE);
      fetch(url)
        .then(function(r) { return r.json(); })
        .then(function(data) {
          var banner = document.getElementById('result-banner');
          var s = data.streak || 0;
          var pts = data.mastered ? 50 : 10;
          _awardKnowledge(pts);
          if (data.mastered) {
            banner.textContent = '🎉 마스터 달성! (3/3) +' + pts + '점 — 잠시 후 오프닝연습 화면으로 이동합니다';
          } else {
            banner.textContent = '✅ 방어 성공! (' + s + '/3) +' + pts + '점 — 3초 후 재시작';
            setTimeout(resetBoard, 3000);
          }
        })
        .catch(function() {
          document.getElementById('result-banner').textContent = '✅ 방어 성공! — 기록 실패';
          setTimeout(resetBoard, 3000);
        });
    });
}

/* 지식 점수 적립 (성공 +10, 마스터 +50) */
function _awardKnowledge(points) {
  if (!USER_ID || !SUPABASE_URL || !SUPABASE_KEY) return;
  var url = SUPABASE_URL + '/rest/v1/users?user_id=eq.' + encodeURIComponent(USER_ID);
  fetch(url + '&select=total_knowledge_score', { headers: _sbHeaders() })
    .then(function(r) { return r.json(); })
    .then(function(rows) {
      if (!rows || !rows.length) return;
      var newScore = (rows[0].total_knowledge_score || 0) + points;
      return fetch(url, {
        method: 'PATCH',
        headers: Object.assign({ 'Prefer': 'return=minimal' }, _sbHeaders()),
        body: JSON.stringify({ total_knowledge_score: newScore }),
      });
    })
    .catch(function() {});
}

/* ── 엔진 수 적용 ─────────────────────────────────────────────────── */
/* Stockfish HTTP → UCI 문자열 ("e2e4") */
function applyUciMove(uci) {
  var move = game.move({ from: uci.slice(0,2), to: uci.slice(2,4),
                         promotion: uci.length > 4 ? uci[4] : 'q' });
  if (!move) return;
  board.position(game.fen());
  updateStatus();
  checkTest();
}
/* JS 미니맥스 → chess.js 수 객체 */
function applyEngineMove(mv) {
  var move = game.move({ from: mv.from, to: mv.to, promotion: mv.promotion || 'q' });
  if (!move) return;
  board.position(game.fen());
  updateStatus();
  checkTest();
}

/* ── 드래그 핸들러 ─────────────────────────────────────────────────── */
function onDragStart(source, piece) {
  if (game.game_over() || testResult !== null) return false;
  if (game.turn() === 'w' && piece.search(/^b/) !== -1) return false;
  if (game.turn() === 'b' && piece.search(/^w/) !== -1) return false;
}

function onDrop(source, target) {
  removeArrows();
  if (userColor === null) userColor = game.turn();
  var move = game.move({ from: source, to: target, promotion: 'q' });
  if (move === null) return 'snapback';
  updateStatus();
  if (game.game_over()) {
    checkTest();
  } else {
    setTimeout(requestBotMove, 420);
  }
}

function onSnapEnd() { board.position(game.fen()); }

/* ── 상태 표시 ─────────────────────────────────────────────────────── */
function updateStatus() {
  var el  = document.getElementById('sv');
  var trn = game.turn() === 'w' ? '백' : '흑';

  if (game.in_checkmate()) {
    el.className = 'status-val over';
    el.textContent = (game.turn() === 'w' ? '흑' : '백') + ' 승리 🎉';
  } else if (game.in_stalemate()) {
    el.className = 'status-val over';
    el.textContent = '스테일메이트 — 무승부';
  } else if (game.in_draw()) {
    el.className = 'status-val over';
    el.textContent = '무승부';
  } else if (game.in_check()) {
    el.className = 'status-val check';
    el.textContent = trn + ' 차례  ⚠ 체크!';
  } else {
    el.className = 'status-val';
    el.textContent = trn + ' 차례';
  }

  var left    = Math.max(0, 7 - interactivePlies());
  var scoreEl = document.getElementById('score-row');
  if (scoreEl) {
    /* 성공 기준은 항상 고정값(-1.0). 실시간 평가는 옆 "엔진 평가" 카드에서 확인 */
    scoreEl.textContent = (left > 0 && testResult === null)
      ? '판정까지 ' + left + '수 남음 (평가 -1.0 이상이면 성공)'
      : '';
  }

  renderMoves();
}

function renderMoves() {
  var hist = game.history();
  var el   = document.getElementById('mv');
  if (!hist.length) {
    el.innerHTML = '<span style="color:#cbd5e1">수를 두면 기록됩니다</span>';
    return;
  }
  var html = '';
  for (var i = 0; i < hist.length; i += 2) {
    html += '<span style="color:#94a3b8">' + (Math.floor(i/2)+1) + '.</span> '
          + hist[i] + (hist[i+1] ? ' ' + hist[i+1] : '') + '&nbsp; ';
  }
  el.innerHTML = html;
  el.scrollTop = el.scrollHeight;
}

/* ── 컨트롤 ─────────────────────────────────────────────────────────── */
function resetBoard() {
  reqId++;
  testResult = null; userColor = null; hintMode = false; pendingBot = false;
  lastEvalCp = 0;
  revengeDerailed = false;
  removeArrows();
  document.getElementById('result-banner').style.display = 'none';
  document.getElementById('eval-num').textContent = '±0.0';
  document.getElementById('eval-num').className = 'eval-num even';
  document.getElementById('eval-white').style.height = '50%';
  document.getElementById('eval-black').style.height = '50%';
  game = buildGame();
  board.position(game.fen(), false);
  updateStatus();
  updateRevengeLabel();
  if (applyRevengeColorLock()) requestInitialEval();
}

/* 리벤지 모드: 유저의 실제 색을 강제 고정. 오프닝 재현 직후가 상대(봇) 차례라면 봇이 먼저 둔다.
   봇이 먼저 두지 않는 경우(=true)를 반환 → 그 경우엔 시작 평가를 따로 한 번 가져온다. */
function applyRevengeColorLock() {
  if (!revengeOn || !userHistColor) return true;
  userColor = userHistColor;
  if (!game.game_over() && game.turn() !== userColor) {
    setTimeout(requestBotMove, 500);
    return false;
  }
  return true;
}

/* 첫 수를 두기 전에도 엔진 평가가 0.0으로 비어있지 않도록, 시작 포지션을 한 번 평가해둔다. */
function requestInitialEval() {
  if (!SF_PORT || game.game_over()) return;
  fetch(sfUrl(game.fen()))
    .then(function(r) { return r.json(); })
    .then(function(data) { if (data.eval) updateEvalFromSF(data.eval); })
    .catch(function() {});
}

function undoMove() {
  if (game.history().length <= openingPlyCount) return;
  reqId++;   /* 진행 중인 fetch 응답(스톡피쉬 수)이 무르기 후 보드에 적용되는 것을 방지 */
  removeArrows();
  pendingBot = false; hintMode = false;
  revengeDerailed = false;   /* 무르면 다시 원본 기보와 일치할 수 있으니 재판정 */
  game.undo();
  if (game.history().length > openingPlyCount) game.undo();
  board.position(game.fen(), false);
  testResult = null;
  document.getElementById('result-banner').style.display = 'none';
  updateStatus();
  updateRevengeLabel();
}

function updateRevengeLabel() {
  var el = document.getElementById('revenge-label');
  if (!revengeOn) { el.style.display = 'none'; return; }
  el.style.display = 'block';
  el.textContent = revengeDerailed
    ? '🗡️ 리벤지 모드 — 과거와 달라져서 이제부터 일반 엔진'
    : '🗡️ 리벤지 모드 — ' + (OPPONENT_NAME || '상대') + '의 실제 수순 재현 중';
}

function flipBoard() { board.flip(); }

function pieceTheme(piece) {
  if (PIECE_URIS && PIECE_URIS[piece]) return PIECE_URIS[piece];
  return 'https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/img/chesspieces/wikipedia/' + piece + '.png';
}

/* ── 초기화 ─────────────────────────────────────────────────────────── */
game = buildGame();
board = Chessboard('board', {
  draggable:     true,
  position:      game.fen(),
  onDragStart:   onDragStart,
  onDrop:        onDrop,
  onSnapEnd:     onSnapEnd,
  pieceTheme:    pieceTheme,
  moveSpeed:     'fast',
  snapbackSpeed: 200,
  snapSpeed:     100,
});
updateStatus();
$(window).resize(board.resize);
setBadge(SF_PORT ? '🟢 Stockfish 16' : '🟢 JS 엔진', true);
updateRevengeLabel();
if (applyRevengeColorLock()) requestInitialEval();
</script>
</body>
</html>"""


def _build_html(
    opening_moves: str,
    skill_level: int,
    depth: int,
    sf_port: int | None,
    user_id: str | None,
    eco_code: str,
    supabase_url: str,
    supabase_key: str,
    revenge_pgn: str,
    opponent_name: str,
    revenge_replay_on: bool,
) -> str:
    safe_moves    = json.dumps(opening_moves).replace("<", "\\u003c").replace(">", "\\u003e")
    safe_uris     = json.dumps(_load_piece_uris())
    safe_revenge  = json.dumps(revenge_pgn).replace("<", "\\u003c").replace(">", "\\u003e")
    safe_opponent = json.dumps(opponent_name)
    return (
        _BOARD_HTML
        .replace("__OPENING_MOVES__", safe_moves)
        .replace("__PIECE_URIS__", safe_uris)
        .replace("__DEPTH__", str(depth))
        .replace("__SKILL_LEVEL__", str(skill_level))
        .replace("__SF_PORT__",  str(sf_port) if sf_port else "null")
        .replace("__USER_ID__",  json.dumps(user_id))
        .replace("__ECO_CODE__", json.dumps(eco_code))
        .replace("__SUPABASE_URL__", json.dumps(supabase_url))
        .replace("__SUPABASE_KEY__", json.dumps(supabase_key))
        .replace("__REVENGE_PGN__", safe_revenge)
        .replace("__OPPONENT_NAME__", safe_opponent)
        .replace("__REVENGE_REPLAY_ON__", "true" if revenge_replay_on else "false")
    )


@st.fragment(run_every="3s")
def _live_streak_panel(user_id: str, eco: str) -> None:
    """보드 안(iframe)에서 Supabase에 직접 기록한 방어 연속/마스터 여부를
    3초마다 다시 읽어와 표시. 이 영역만 다시 그려지고 체스보드는 그대로 유지된다.
    마스터를 달성한 순간을 감지하면 축하 메시지를 띄우고 오프닝연습 탭으로 돌아간다."""
    detail   = get_opening_detail(user_id, eco)
    streak   = detail.get("defense_streak", 0) if detail else 0
    mastered = detail.get("is_mastered", False) if detail else False

    streak_txt = "🟦" * streak + "⬜" * (3 - streak) + f"  {streak}/3"
    st.metric("방어 연속", streak_txt)

    celebrated_key = f"_celebrated_{eco}"
    if mastered and not st.session_state.get(celebrated_key):
        st.session_state[celebrated_key] = True
        st.success("🎉 축하합니다! 마스터하셨습니다!")
        st.balloons()
        time.sleep(1.5)
        st.session_state.current_page = "skill_tree"
        st.session_state.selected_eco = None
        st.rerun()


# ── 메인 렌더러 ───────────────────────────────────────────────────────────────

def render_training() -> None:
    if st.button("← 스킬 트리로 돌아가기"):
        st.session_state.current_page = "skill_tree"
        st.rerun()

    user_id = st.session_state.get("user_id")
    if not user_id:
        st.warning("먼저 홈 화면에서 닉네임을 입력해주세요.")
        if st.button("홈으로 이동"):
            st.session_state.current_page = "home"
            st.rerun()
        return

    eco = st.session_state.get("selected_eco")
    if not eco:
        st.warning("훈련할 오프닝이 선택되지 않았습니다. 스킬 트리에서 오프닝을 선택해주세요.")
        return

    detail = get_opening_detail(user_id, eco)

    eco_name        = eco
    opening_moves   = ""
    loss_count      = 0
    opponent_name   = ""
    full_lost_pgn   = ""

    if detail:
        eco_ref       = detail.get("eco_reference") or {}
        eco_name      = eco_ref.get("name") or eco
        opening_moves = detail.get("last_lost_sequence") or _DEFAULT_SEQUENCES.get(eco, "")
        loss_count    = detail.get("loss_count", 0)
        opponent_name = detail.get("opponent_username") or ""
        full_lost_pgn = detail.get("full_lost_pgn") or ""

    # ── 헤더 ──────────────────────────────────────────────────────────────────
    st.markdown(f"## ⚔️ 훈련: {eco_name}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ECO 코드", eco)
    c2.metric("패배 횟수", f"{loss_count}회")
    with c3:
        _live_streak_panel(user_id, eco)

    difficulty = c4.selectbox(
        "봇 난이도",
        list(_DIFFICULTY_MAP.keys()),
        index=1,
        label_visibility="visible",
    )
    skill_level, depth = _DIFFICULTY_MAP[difficulty]

    if opening_moves:
        st.caption(f"패배 오프닝 재현 후 훈련 시작: `{opening_moves}`")
    else:
        st.caption("초기 포지션에서 훈련합니다.")

    # ── 리벤지 모드 ──────────────────────────────────────────────────────────
    revenge_available = bool(full_lost_pgn)
    revenge_on = False
    if revenge_available:
        revenge_on = st.checkbox(
            f"🗡️ 리벤지 모드 — **{opponent_name or '상대'}** 가 실제로 둔 수를 그대로 재현",
            value=False,
            help="이 오프닝에서 나를 이긴 상대의 실제 기보를 봇이 재현합니다. "
                 "내가 과거와 다른 수를 두는 순간부터는 일반 엔진이 이어받습니다.",
        )
    else:
        st.caption("🗡️ 리벤지 모드: 이 오프닝은 아직 실제 패배 기보가 없어 사용할 수 없습니다 (Chess.com 분석 필요).")

    st.divider()

    # ── 체스보드 ──────────────────────────────────────────────────────────────
    sb_url = st.secrets["supabase"]["url"]
    sb_key = st.secrets["supabase"]["key"]

    import engine as _engine
    _engine.init(sb_url, sb_key)
    sf_port = _engine.get_port()
    components.html(
        _build_html(
            opening_moves, skill_level, depth, sf_port, user_id, eco, sb_url, sb_key,
            full_lost_pgn, opponent_name, revenge_on,
        ),
        height=540, scrolling=False,
    )
