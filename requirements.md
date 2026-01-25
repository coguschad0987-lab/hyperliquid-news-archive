# requirements.md — X(Twitter) News URL Collector

## 1. 목적
- 사용자가 **로그인된 X(트위터) 계정** 기준으로,
  - 홈 타임라인의 **Following 탭** 및 **Notifications 탭**에서 노출되는 게시물을 확인하고
  - **실행 시각 기준 최근 24시간(rolling 24h)** 동안 발생한 이벤트(게시/재게시/인용)만 대상으로
  - **현재 화면에 표시되는 Views 기준 상위 20개 “원문” URL**을 추출하여
  - 날짜별 파일로 누적 저장하고,
  - 별도 Git 저장소로 결과물을 복사한 뒤 **Git CLI로 commit/push**까지 자동 수행한다.
- 이 데이터는 향후 더 복잡한 자동화/분석 파이프라인의 입력으로 사용한다.

## 2. 핵심 결정사항(확정)
- Views 기준: **현재 화면에 표시된 Views 숫자**(약어 포함)를 정수로 파싱
- Views 미표시: 후보 카드에 없으면 **상세 페이지 진입 후 확인**, 끝내 확인 불가 시 **제외**
- 시간 범위: 최근 24시간 내 이벤트만 대상(게시/재게시/인용)
- Quote 처리:
  - 최종 Top20은 **원문만 포함**
  - Quote는 **원문 background 확인용**으로 **별도 JSON 파일**에 매핑 저장
- Repost 처리:
  - 최근 24시간 내 Repost 이벤트는 대상
  - 최종 결과는 **원문 URL만** 남기며 중복은 제거
- 소스 범위: 홈 타임라인의 **Following 탭** + **Notifications 탭**
- GitHub 연동: 결과 파일을 **별도 repo로 복사** 후 `git add/commit/push` 수행
  - repo 내 저장 경로: `data/news/`
- 자동 실행: **매일 09:00 KST**
- 로그: 로컬에만 저장(`/logs/`), **repo에는 커밋하지 않음**

## 3. 접근 방식 및 인증(로그인)
### 3.1 브라우저 자동화
- Playwright 등 브라우저 자동화 기반으로 X 웹에 접근한다.
- “로그인된 크롬 계정”을 사용하기 위해 다음 중 1개 방식을 지원해야 한다(구현 시 택1 또는 둘 다 지원):
  1) **Chrome 프로필 디렉토리 지정 방식(권장)**  
     - 사용자가 실제로 로그인해 둔 Chrome 프로필을 그대로 사용해 로그인 상태를 재사용한다.
     - 입력: `--chrome-profile-dir` (Chrome User Data 경로 + Profile 이름/디렉토리)
  2) **Playwright persistent auth state 방식**  
     - 최초 실행에서 브라우저를 열고 사용자가 로그인 후 세션을 저장, 이후 재사용한다.
     - 입력: `--user-data-dir` 또는 `--auth-state-path`

### 3.2 로그인 필요 상태 표준화(Exit code/메시지)
- 로그인 상태가 아닐 경우 프로그램은:
  - 출력 메시지: `로그인이 필요합니다. 지정한 Chrome 프로필로 X에 로그인한 뒤 다시 실행하세요.`
  - 종료 코드(예): `2`
  - 파일 생성/복사/커밋/푸시는 수행하지 않는다.

## 4. 수집 대상 및 범위
### 4.1 수집 소스
- 홈 타임라인의 Following 탭
- Notifications 탭

### 4.2 시간 범위 규칙(최근 24시간)
- 실행 시각 `T` 기준 **(T - 24시간) ~ T** 사이에 발생한 이벤트만 수집한다.
- 이벤트 시각 판단 기준:
  - Post: 게시 시각
  - Quote: 인용 시각(단, 최종 리스트에는 포함하지 않음)
  - Repost: **재게시 시각**
    - 원문이 24시간 이전이라도, 재게시가 24시간 내면 대상
    - 24시간 이전에 재게시된 항목은 제외

### 4.3 스크롤/수집 제한(무한 스크롤 제어)
- 설정 가능한 파라미터(기본값 포함):
  - 최대 스크롤 횟수(예: 40)
  - 최대 후보 수(예: 400)
  - 최대 실행 시간/타임아웃(예: 180초)
- 최근 24시간 범위를 명확히 벗어난 항목이 연속으로 등장하면 조기 종료 가능

## 5. 데이터 추출 요구사항
### 5.1 후보 항목 필드
각 후보에서 최소 다음을 수집/계산한다:
- 원문 트윗 URL(최종 결과 저장 대상)
- 후보 항목 URL(Quote/Repost 자체 URL)
- Views(정수)
- 이벤트 타입: Post / Repost / Quote
- 이벤트 시각(최근 24시간 필터링용)
- 중복 판정용 ID(트윗 ID 등)

### 5.2 Views 파싱(약어 → 정수)
- 약어를 정수로 변환:
  - `1.2K` → 1200
  - `1M` → 1000000
- 소수점/콤마/공백 등 UI 변형을 고려한다.
- 카드에 Views가 없으면 상세 페이지로 진입해 확인한다.
- 상세 페이지에서도 Views 확인 불가 시 **해당 후보는 제외**한다.

## 6. 선별/정제 규칙
### 6.1 중복 제거 및 정규화
- 최종 리스트는 **원문 URL 기준**으로 유일해야 한다.
- Post/Repost/Quote로 여러 경로에서 같은 원문이 수집되어도 최종 1개만 유지한다.

### 6.2 Quote 처리(확정)
- Quote는 최종 Top20에서 제외한다.
- Quote는 별도 저장(원문 background 확인용)한다:
  - 원문 URL → Quote URL 목록 매핑
  - 최근 24시간 내 Quote 이벤트만 포함

### 6.3 Repost 처리(확정)
- Repost는 최근 24시간 내 Repost 이벤트 기준으로 포함한다.
- 최종 리스트에는 Repost URL이 아닌 **원문 URL만** 남긴다.

### 6.4 Top 20 선정
- 최근 24시간 범위 조건을 만족하고 Views가 확인된 원문 후보 중
  - Views 내림차순 정렬
  - 상위 20개 원문 URL 선정

## 7. 출력 및 저장
### 7.1 콘솔 출력
- Top 20 원문 URL을 1줄 1개로 출력한다.
- 실행 요약 로그를 함께 출력한다:
  - 수집 후보 수 / 최근 24h 통과 수 / dedupe 후 원문 수 / 최종 20개 수
  - Quote 매핑(원문 수, quote 수)

### 7.2 로컬 저장(필수, 고정 경로)
- 로컬 저장 경로(고정):  
  `/Users/imchaehyeon/Desktop/Vibe Coding/Twitter News`
- 파일:
  1) 원문 URL 파일: `YYYY-MM-DD.txt`
     - 내용: 원문 URL 1줄 1개, 최대 20줄
  2) Quote 매핑 JSON: `YYYY-MM-DD.quotes.json`
     - 내용(예시 구조):
       ```json
       {
         "generated_at": "2026-01-24T09:00:00+09:00",
         "window_hours": 24,
         "mapping": {
           "ORIGINAL_URL_1": ["QUOTE_URL_A", "QUOTE_URL_B"],
           "ORIGINAL_URL_2": []
         }
       }
       ```

### 7.3 로그 파일 저장(로컬 전용)
- 로그 디렉토리: 프로젝트 실행 위치 기준 `/logs/` 또는 절대 경로로 지정 가능한 `/logs/`
- 로그 파일명 권장:
  - `logs/YYYY-MM-DD.log`
- 로그는 **Git repo에 복사/커밋하지 않는다.**

### 7.4 파일 쓰기 안정성
- 디렉토리가 없으면 자동 생성한다.
- 파일 작성은 임시 파일로 먼저 저장 후 원자적 rename을 권장한다.
- 일부 단계 실패 시에도 가능한 범위에서 부분 결과를 저장하고, 최소한 실패 로그는 남긴다.

## 8. 실행 방식
### 8.1 수동 실행
- 단일 커맨드로 실행 가능해야 한다(예: `python main.py`).
- 주요 옵션(플래그/환경변수):
  - `--headless=[true|false]`
  - `--max-scrolls`, `--timeout`, `--max-candidates`
  - `--window-hours` (기본 24)
  - `--output-dir` (기본은 고정 경로지만 테스트용 override 허용 권장)
  - `--git=[on|off]` (기본 on)
  - `--repo-dir` (별도 Git repo 경로)
  - `--repo-subdir` (기본 `data/news/`)
  - `--chrome-profile-dir` 또는 `--user-data-dir`/`--auth-state-path`

### 8.2 자동 실행(매일 09:00 KST)
- macOS 기준 자동 실행 지원:
  - 우선순위: `launchd` (권장), 대안: crontab
- 자동 실행 시:
  - headless 기본값: true
  - 로그 파일은 로컬 `/logs/`에 기록

## 9. Headless 모드 요구사항(필수)
- 디버깅 단계에서는 headless=false로 브라우저를 표시 가능해야 한다.
- 안정화 후에는 headless=true로 백그라운드 실행 가능해야 한다.
- 사용자는 옵션으로 언제든 전환할 수 있어야 한다.

## 10. GitHub 연동(Git CLI, 별도 repo로 복사)
### 10.1 동작 순서(확정)
1) 로컬 고정 경로에 결과 파일 생성  
   - `/Users/imchaehyeon/Desktop/Vibe Coding/Twitter News/YYYY-MM-DD.txt`  
   - `/Users/imchaehyeon/Desktop/Vibe Coding/Twitter News/YYYY-MM-DD.quotes.json`
2) 지정된 Git repo 경로(`--repo-dir`)로 결과 파일 복사
3) repo 내 `data/news/`에 저장(없으면 생성)
4) Git CLI 실행(working dir: repo root):
   - `git add data/news/YYYY-MM-DD.txt data/news/YYYY-MM-DD.quotes.json`
   - `git commit -m "Add X links: YYYY-MM-DD"`
   - `git push`

### 10.2 실패 처리
- Git 단계 실패 시:
  - 실패 원인을 명확히 출력(인증/remote/충돌 등)
  - 로컬 결과 파일은 유지한다(유실 금지)

## 11. 에러 핸들링 및 복원력(필수)
- 네트워크 끊김/지연/타임아웃:
  - 재시도(지수 backoff) 정책 적용
- X 레이아웃/셀렉터 변경:
  - 셀렉터를 한 파일/한 모듈로 중앙화
  - 셀렉터 실패 시 “레이아웃 변경 가능” 진단 로그 출력
- 어떤 경우에도 파일 작성이 완전히 실패하지 않도록:
  - 부분 결과 저장 시도
  - 최소 실패 로그 저장

## 12. 비범위(Out-of-Scope)
- 다중 계정 지원
- 서버 배포/웹 UI
- 공식 X API 기반 완전 대체(추후 옵션)
- 비밀번호 직접 입력/저장(프로필/세션 재사용만)

## 13. 성공 기준(Acceptance Criteria)
- 로그인 상태에서 실행 시:
  - Following+Notifications에서 최근 24시간 내 이벤트 기반으로 후보 수집
  - Views를 정수로 파싱(필요 시 상세 진입)하고 미확인 후보는 제외
  - Quote는 Top20에서 제외하되 `YYYY-MM-DD.quotes.json`으로 매핑 저장
  - Views 상위 20개 원문 URL을 `YYYY-MM-DD.txt`로 저장 및 출력
  - 결과 파일을 지정 repo의 `data/news/`로 복사 후 Git CLI로 commit/push 완료
  - 로그는 로컬 `/logs/`에만 저장
- 로그아웃 상태에서 실행 시:
  - 표준 메시지 + exit code로 로그인 필요를 반환
