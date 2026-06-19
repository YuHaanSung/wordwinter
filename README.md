# Opening Flex

체스 오프닝 약점 분석 & 맞춤 훈련 플랫폼 (데이터베이스 프로젝트)

## 핵심 기능
- Chess.com 닉네임을 입력하면 실제 기보를 분석해 자주 패배하는 오프닝 라인을 식별
- 식별된 약점은 스킬 트리에서 점멸 표시되며, 클릭하면 해당 오프닝 훈련으로 이동
- 훈련 보드는 Stockfish 16 엔진과 직접 대결 (백그라운드 HTTP 브릿지로 연동)
- **리벤지 봇**: 나를 이겼던 상대의 실제 수순을 그대로 재현하는 맞춤형 훈련
- 평가가 무너지는 지점(블런더 지점)을 자동으로 찾아 그 직전부터 훈련 시작
- 힌트 기능: 정석 추천 수 + 공격적 대안 수를 색으로 구분해 동시 제시
- 방어에 3연속 성공하면 마스터 처리 + 지식 점수 획득, 점수에 따라 브론즈~다이아몬드 티어 부여
- 통계, 사이트 추천, 마이페이지 등 부가 화면 제공

## 기술 스택
- **Frontend/App**: Streamlit
- **DB**: Supabase (PostgreSQL + PostgREST)
- **체스 엔진**: Stockfish 16 (Python `stockfish` 패키지로 로컬 HTTP 브릿지 구성)
- **체스 UI**: chessboard.js + chess.js (iframe 컴포넌트)
- **외부 데이터**: Chess.com Published API

## 로컬 실행
```bash
pip install -r requirements.txt
# .streamlit/secrets.toml.example 을 참고해 .streamlit/secrets.toml 작성
streamlit run app.py
```

## 배포
Streamlit Community Cloud에서 이 저장소를 연결하고, `Main file path`를 `app.py`로 지정.
Supabase 접속 정보는 Streamlit Cloud의 **Secrets** 설정에 다음 형식으로 입력:
```toml
[supabase]
url = "https://your-project.supabase.co"
key = "your-anon-or-publishable-key"
```
