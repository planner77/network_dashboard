# 실패 원장 (FAILURE_LEDGER.md)

> **참조 안내**: 본 문서는 `AGENTS.md`의 5단계 필수 절차인 **실패 원장 기록**을 관리하는 문서입니다. 분석, 설계, 구현, 로컬 테스트, 원격 푸시, GHCR 게시 전 과정에서 발생한 문제점, 불합리한 가정, 빌드/런타임 오류, 명령 실패 및 그 해결 과정을 투명하게 기록합니다.

---

## 기록 양식 (Ledger Schema)
- **ID**: `FL-XXX`
- **발생 일시**: `YYYY-MM-DD HH:MM (KST)`
- **진행 단계**: `분석` | `설계` | `구현` | `로컬 테스트` | `원격 푸시` | `GHCR 게시`
- **증상 / 문제 정의**: 발생한 오류 메시지 또는 발견된 불합리성
- **근본 원인 (Root Cause)**: 문제가 발생한 기술적/구조적 원인
- **해결 조치 (Resolution)**: 적용한 수정 사항 및 우회/해결 방법
- **재발 방지 대책 (Prevention)**: 동일 문제 방지를 위한 아키텍처 또는 체크리스트 반영 사항

---

## 실패 및 개선 이력 (Recorded Entries)

### `FL-001` — 초기 런타임 도구 점검 시 `docker-compose` V1 바이너리 부재로 인한 종료 코드 1 발생
- **발생 일시**: `2026-11-15 13:31 (KST)`
- **진행 단계**: `분석` (환경 조사)
- **증상 / 문제 정의**: `which docker docker-compose python3 node npm git` 실행 시 `docker-compose`(하이픈 연결 독립 실행 파일)가 존재하지 않아 명령이 Exit Code `1`을 반환함.
- **근본 원인**: 최신 Docker 환경(Docker Compose v5.5.1)에서는 `docker-compose` 독립 바이너리 대신 Docker CLI 플러그인 형태인 `docker compose`(공백 구분)를 표준으로 사용함.
- **해결 조치**: `docker compose version` 명령으로 Docker Compose v5.5.1 정상 설치를 확인하고, 이후 모든 스크립트와 문서에서 `docker compose` 표준 명령어를 사용하도록 통일함.
- **재발 방지 대책**: `ARCHITECTURE.md` 및 `README.md`의 실행 스크립트에서 구형 `docker-compose` 대신 `docker compose` 및 단일 `docker run` 명령을 표준으로 명시.

### `FL-002` — 30초 소켓 상태 보고 주기와 무선 단절 사전 감지(Pre-detection) 간의 구조적 불합리성 발견
- **발생 일시**: `2026-11-15 13:32 (KST)`
- **진행 단계**: `분석 및 설계`
- **증상 / 문제 정의**: 기존 요구 배경인 "30초 주기 소켓 상태 보고"만으로는 수 초(3~15초) 내에 진행되는 AP 로밍 실패나 음영지역 진입을 **사전 감지**하는 것이 물리적으로 불가능함(나이퀴스트 샘플링 한계 위배).
- **근본 원인**: 무선 신호 감쇠 및 TCP 재전송 백오프는 1~10초 단위의 현상인데 반해, 상위 보고 주기는 30초로 고정되어 있어 샘플링 주기가 현상 변화 시간보다 김.
- **해결 조치**: 사용자와의 질의응답(`ask_question`)을 통해 **3단계 하이브리드 수집 모델**(① AGV 내부 1초 주기 경량 링버퍼 수집 → ② 평시 30초 보고 시 통계 요약치 피기백 → ③ 위험 점수 임계 초과 시 조기 경보 즉시 푸시 및 재연결 후 1초 단위 블랙박스 덤프)로 설계를 합리화함.
- **재발 방지 대책**: `docs/ANALYSIS_AND_METRICS.md`에 하이브리드 수집 아키텍처를 표준으로 명문화하고, Mock-up 사이트의 차트에서도 `1초 로컬 수집 데이터`와 `30초 ACS 보고 시점`을 오버레이하여 왜 하이브리드 수집이 필수인지 시각적으로 증명하도록 설계 반영.

### `FL-003` — 초기 작업 디렉토리 Git 미초기화 상태 및 `.env` 민감 토큰 노출 위험
- **발생 일시**: `2026-11-15 13:36 (KST)`
- **진행 단계**: `분석 및 설계`
- **증상 / 문제 정의**: `git status` 실행 시 `fatal: not a git repository` 오류 발생. 또한 작업 폴더 내 `.env` 파일에 GitHub Personal Access Token(`ghp_...`)이 평문으로 존재하여, 무분별한 `git add .` 또는 `docker build .` 실행 시 원격 저장소 및 GHCR 이미지에 시크릿이 유출되거나 GitHub Push Protection에 의해 푸시가 차단될 위험이 있음.
- **근본 원인**: 초기 워크스페이스가 `.env` 파일만 포함된 비-Git 디렉토리 상태로 시작됨.
- **해결 조치**: 첫 커밋 전에 `.gitignore`에 `.env`, `.env.*`, `*.db` 등을 최우선 등록하고 `git init -b main`으로 저장소를 초기화함.
- **재발 방지 대책**: `Dockerfile` 작성 시 `.dockerignore`에도 `.env` 및 `.git`을 반드시 제외하도록 `AGENTS.md` 보안 수칙에 강제함.

### `FL-004` — 멀티 에이전트 병렬 구현 중 Claude 계열 모델 쿼터 소진 (`RESOURCE_EXHAUSTED 429`) 발생
- **발생 일시**: `2026-11-15 13:59 ~ 14:04 (KST)`
- **진행 단계**: `구현` (에이전트 병렬 작업)
- **증상 / 문제 정의**: `domain-analyst`에 할당된 `claude-opus-5-5-high` 모델과 `backend-tsdb`에 할당된 `claude-sonnet-5-5-high` 모델에서 `RESOURCE_EXHAUSTED (code 429): Individual quota reached` 오류가 발생하며 턴이 중단됨.
- **근본 원인**: 대용량 도메인 명세(18종 지표 + 4대 시나리오 120초 시계열) 생성 중 개별 모델의 시간당 토큰/요청 쿼터 한도에 도달함.
- **해결 조치**: `AGENTS.md`의 모델 운용 규칙에 따라 워커를 강제 종료(`kill`)하지 않고 `swarm{action:"model", name:"domain-analyst"}` 및 `swarm{action:"model", name:"backend-tsdb"}`를 호출하여 작업 컨텍스트를 그대로 유지한 채 코디네이터 기본 모델(`gemini-4-argon-medium`)로 무중단 전환(Hot-switch)하여 `app/metrics_catalog.py` 구현을 완료함.
- **재발 방지 대책**: 스웜 워커 운용 시 쿼터 소진 이벤트가 발생하면 컨텍스트 손실이 발생하는 재생성(`kill` + `add`) 대신 즉시 `swarm model` 전환을 수행하는 절차를 표준화함.

### `FL-005` — 병렬 모듈 개발 시 파일 생성 시점 차이에 따른 초기 Import/라우팅 의존성 불일치
- **발생 일시**: `2026-11-15 13:54 (KST)`
- **진행 단계**: `구현 및 로컬 테스트`
- **증상 / 문제 정의**: `backend-tsdb`가 `app/main.py`를 먼저 완성하여 단독 테스트했을 때, 아직 `domain-analyst`의 `app/metrics_catalog.py` 내 `FAILURE_SCENARIOS`와 `frontend-ui`의 `app/static/index.html`이 생성 완료되기 전이어서 초기 테스트 시 `/api/scenarios` 및 `GET /`가 일시적으로 빈 값/404를 반환함.
- **근본 원인**: 4명의 에이전트가 동시에 병렬로 각자 담당 파일을 작성함에 따라 모듈 간 완성 시점 차이가 발생함.
- **해결 조치**: `app/main.py`에서 `metrics_catalog` 심볼을 동적/방어적으로 참조하도록 구현하고, 모든 에이전트가 `[done]`을 보고한 직후 `pytest tests/test_api.py -v` 통합 테스트(9개 테스트 케이스)를 재실행하여 전 엔드포인트 `200 OK` 및 데이터 정합성을 최종 확인함.
- **재발 방지 대책**: 병렬 에이전트 개발 시 모듈 간 인터페이스 계약(Contract)을 브리프에 사전 정의하고, 모든 워커 완료 후 `devops-qa`가 통합 E2E 테스트를 수행하는 2단계 검증 게이트를 적용함.

### `FL-006` — 샌드박스 내부에서 Docker 데몬 소켓(`/var/run/docker.sock`) 및 `~/.docker/buildx` 접근 차단
- **발생 일시**: `2026-11-15 14:09 (KST)`
- **진행 단계**: `로컬 테스트 및 GHCR 게시`
- **증상 / 문제 정의**: 기본 샌드박스 모드(`BypassSandbox: false`)에서 `docker build` 및 `docker images` 실행 시 `mkdir /home/planner/.docker/buildx: read-only file system` 및 `dial unix /var/run/docker.sock: connect: no such file or directory` 오류 발생.
- **근본 원인**: 샌드박스 격리 정책상 호스트의 Docker 소켓(`/var/run/docker.sock`)과 홈 디렉토리 쓰기 권한 및 외부 네트워크(GitHub/GHCR) 접근이 차단되어 있음.
- **해결 조치**: 코드 스테이징, 로컬 단위 테스트(`pytest`), Git 커밋 등 로컬 파일시스템 작업은 샌드박스 내부에서 완료하고, 호스트 Docker 데몬 및 외부 네트워크 통신이 필수적인 `docker build`, `git push`, `docker push` 명령만 단일 명령 단위로 `BypassSandbox: true`를 사용하여 실행함.
- **재발 방지 대책**: 샌드박스 외부 실행이 필요한 명령(Docker 빌드/푸시, Git 원격 푸시)은 복합 체인(`&&`)을 지양하고 최소한의 단일 명령으로 분리하여 실행함.

### `FL-007` — 투어 가이드 3단계 하이라이트 위치 어긋남 및 테두리 시인성 부족
- **발생 일시**: `2026-11-15 17:59 (KST)`
- **진행 단계**: `UI/UX 검증 및 개선 (v1.1)`
- **증상 / 문제 정의**: 투어 가이드 진행 시 대상 영역이 얇은 테두리로만 표시되어 시인성이 떨어지고, 특히 3단계(2D 공장 맵 패널) 설명 시 하이라이트 테두리가 실제 패널이 아닌 엉뚱한 좌표에 위치함.
- **근본 원인**: `scrollIntoView({ behavior: "smooth" })`가 비동기로 스크롤 애니메이션을 수행하는 도중에 즉시 `getBoundingClientRect()`를 호출하여 스크롤 완료 전의 뷰포트 좌표가 고정(`position: fixed`) 스포트라이트에 적용되었고, 스크롤/리사이즈 이벤트 시 재계산 리스너가 없었음.
- **해결 조치**: `scrollIntoView({ behavior: "instant", block: "center" })`로 즉시 이동 후 `requestAnimationFrame` 및 `window`의 `scroll`(캡처 단계)/`resize` 이벤트마다 좌표를 실시간 재계산하도록 수정함. 또한 대상 요소 자체에 `.tour-active-target`(이중 고대비 포커스 광채 + 밝은 표면 강조)과 상단 `📍 현재 설명 영역 — Step N / 8` 플로팅 배지를 추가하여 시인성을 대폭 강화함.
- **재발 방지 대책**: `DESIGN.md`에 스포트라이트 투어 구현 시 비동기 스무스 스크롤 후 즉시 좌표 측정 금지 및 실시간 스크롤 추적 규칙을 명문화함.

### `FL-008` — 상단 1줄 헤더에서 'Live' 상태 배지와 첫 번째 탭 겹침 및 수집 항목 일람표 스크롤 시 헤더 미고정
- **발생 일시**: `2026-11-15 17:59 (KST)`
- **진행 단계**: `UI/UX 검증 및 개선 (v1.1)`
- **증상 / 문제 정의**: 상단 헤더의 좌측 'Live' 상태 표시 구성 요소와 중앙 첫 번째 탭(`실시간 관제 & 2D 맵`)이 겹쳐 보이고, `3. 수집 항목 백과사전 (18종)`의 일람표를 스크롤할 때 테이블 헤더가 함께 올라가 컬럼 구분이 불편함.
- **근본 원인**: 단일 행(`height: 60px`) 안에 브랜드 타이틀, 상태 배지, 탭 메뉴, 우측 버튼들을 모두 배치하여 가로 공간 부족 시 충돌이 발생했으며, 일람표 컨테이너에 고정 높이 스크롤 및 `position: sticky` 헤더가 누락됨.
- **해결 조치**: 상단 헤더(`.global-navbar`)를 **2단 구조**(1단: 시스템 타이틀 + 시계열 수집 상태 배지 + 우측 투어/테마 버튼, 2단: 5개 메인 탭 바)로 분리하여 요소 간 겹침을 원천 차단하고, 일람표(`.catalog-table-scroll`)에 `max-height: 460px; overflow-y: auto;` 및 `thead th { position: sticky; top: 0; z-index: 25; }`를 적용하여 헤더를 고정함. 또한 기본 테마를 가독성이 뛰어난 **라이트 테마(`data-theme="light"`)**로 전환함.
- **재발 방지 대책**: `DESIGN.md`에 2단 헤더 레이아웃과 데이터 테이블 Sticky Header 표준을 필수 규칙으로 반영함.

### `FL-009` — 개발자 중심 전문 용어(피기백, 링버퍼, 주입, 내장 TSDB) 및 AP/WLC 수집 의존성 개선
- **발생 일시**: `2026-11-15 17:59 (KST)`
- **진행 단계**: `분석·설계·구현 고도화 (v1.1)`
- **증상 / 문제 정의**: '피기백', '1초 고주파 링버퍼', '시나리오 주입', '내장 시계열 DB' 등 개발자에게만 익숙한 용어가 사용되었고, 수집 항목에 현장 무선 인프라(AP/WLC) 수집 위치가 혼재되어 있었으며, AGV 담당자와 ACS 담당자의 역할 요약 탭 및 `.env` 기반 `9921` 포트 설정이 필요함.
- **근본 원인**: 초기 설계 시 엔지니어링 약어를 UI에 그대로 노출했고, AP/WLC 장비 접근이 불가능한 현장 여건을 고려한 `AGV/AMR` 및 `ACS` 양단 수집 한정이 엄격히 적용되지 않았음.
- **해결 조치**:
  1. 모든 전문 용어를 일반 사용자 친화적 표현(`30초 정기 보고 시 요약 데이터 동봉 전송`, `AGV 내부 1초 단위 상시 기록장`, `장애 상황 가상 체험`, `실제 운영 시 시계열 DB 도입 필요성`)으로 전면 개편.
  2. 18종 수집 항목 전수를 **`AGV/AMR`과 `ACS`에서만 직접 수집 가능한 항목**으로 재정비.
  3. **`5. 담당자별 해야 할 일 (AGV & ACS)`** 탭을 신설하여 AGV/AMR 담당자 5대 과업과 ACS 담당자 4대 과업을 명확히 요약.
  4. `.env` 및 `docker-compose.yml`을 통해 접속 포트(`9921`)와 주요 설정을 일괄 관리하도록 구성하고 `README.md`에 변경 이력(Changelog)을 반영함.
- **재발 방지 대책**: `AGENTS.md`의 Golden Rules에 쉬운 용어 사용 수칙, `AGV/AMR` 및 `ACS` 수집 한정 원칙, `.env` 포트(`9921`) 관리 원칙을 최우선 수칙으로 등록함.

### `FL-010` — 투어 가이드 툴팁 상자 고정 위치로 인한 화면 가림 개선 및 7대 핵심 지표 키워드 명시 보완
- **발생 일시**: `2026-11-15 18:45 (KST)`
- **진행 단계**: `UI/UX 및 수집 지표 명세 보완 (v1.1.1)`
- **증상 / 문제 정의**: 투어 가이드 툴팁 상자(`#tour-popover`)가 우측 하단에 고정되어 있어 사용자가 뒤쪽 화면 요소를 볼 때 원하는 위치로 옮길 수 없었으며, `Tx/Rx Retry Rate`, `TCP Socket State`, `Send/Recv Queue`, `MCS Index`, `Heartbeat Timeout`, `Ping Latency`, `Packet Loss` 항목이 18종 중 어느 항목에 포함·통합되어 있는지 직관적인 표기가 필요함.
- **근본 원인**: 투어 팝오버에 마우스/터치 드래그 이벤트 핸들러가 없었고, 일부 항목(`M04`, `M05`, `M09`, `M15`, `M16`)이 한글 중심 명칭으로만 되어 있어 영문 표준 키워드로 검색 시 매핑 관계를 한눈에 알기 어려웠음.
- **해결 조치**:
  1. `#tour-popover-header`에 마우스(`mousedown`/`mousemove`/`mouseup`) 및 터치 드래그 이동 로직과 `✥ 이동` 핸들을 추가하고, 더블클릭 시 기본 위치로 복귀하도록 구현.
  2. `M04`(`PHY Rate & MCS Index`), `M05`(`Tx/Rx Retry Rate`), `M09`(`Ping Latency & Packet Loss`), `M13/M14`(`Send/Recv Queue`), `M15`(`Heartbeat Timeout`), `M16`(`TCP Socket State`)의 제목과 상세 설명에 해당 키워드와 수집 방법을 명확히 병기.
- **재발 방지 대책**: `tests/test_api.py`에 드래그 핸들 존재 여부 및 7대 키워드 포함 여부 검증 테스트를 추가함.

### `FL-011` — GitHub 저장소 Packages 섹션에 GHCR 이미지가 자동 연결·표시되지 않는 현상 및 이미지 내 Mock-up DB 사전 적재
- **발생 일시**: `2026-11-15 19:01 (KST)`
- **진행 단계**: `GHCR 배포 및 패키징 보완 (v1.1.2)`
- **증상 / 문제 정의**: `ghcr.io/planner77/network_dashboard` 이미지를 푸시했으나 GitHub 저장소(`https://github.com/planner77/network_dashboard`) 우측 `Packages` 섹션에 목록이 표시되지 않았으며, 이미지 내부에도 초기 Mock-up 데이터 스냅샷이 기본 포함되도록 보장 필요.
- **근본 원인**: GitHub Container Registry(GHCR)는 `Dockerfile`에 OCI 표준 레이블(`LABEL org.opencontainers.image.source="https://github.com/planner77/network_dashboard"`)이 명시되어 있어야 푸시 시 해당 저장소의 `Packages` 섹션에 자동 연결됨. 또한 기존에는 컨테이너 기동 시점에 Mock-up 데이터를 생성하고 있어 빌드 시점 이미지 레이어 내부의 `/app/tsdb_data/network_telemetry.db` 파일 사전 생성이 없었음.
- **해결 조치**:
  1. `Dockerfile`에 `LABEL org.opencontainers.image.source="https://github.com/planner77/network_dashboard"` 등 OCI 표준 메타데이터 레이블을 추가하여 GHCR 이미지와 GitHub 저장소를 자동 연결.
  2. `Dockerfile` 빌드 단계에서 `TSDB('/app/tsdb_data/network_telemetry.db').seed_initial_data(force=True)` 및 WAL 체크포인트를 수행하여 **이미지 자체에 초기 Mock-up 시계열 DB 파일(AGV 6대 × 10분 이력 3,600건, 30초 보고 120건, 4대 장애 이력)이 물리적으로 포함**되도록 하고, 컨테이너 기동 시에는 현재 시각 기준으로 최신 시계열 데이터를 자동 갱신·실시간 생성하도록 구성.
- **재발 방지 대책**: 모든 GHCR 배포용 `Dockerfile` 작성 시 `org.opencontainers.image.source` 레이블을 필수 포함하도록 표준화함.

### `FL-012` — MIMO 안테나별 신호 세기, 채널 상세 정보, 링크 종합 품질 누락 보완 및 4대 핵심 분석 구조(의미·문제상황·사전감지·사후분석) 분리 표현
- **발생 일시**: `2026-11-16 06:21 (KST)`
- **진행 단계**: `분석·설계·구현 고도화 (v1.1.3)`
- **증상 / 문제 정의**: 기존 18종 수집 지표에서 ① `M01(RSSI)`이 합산 신호 세기 1개만 수집하여 **2×2 MIMO 안테나 환경에서 한쪽 안테나 커넥터 단선이나 회전 시 차체 가림(Chain Imbalance)**을 감지할 수 없었고, ② `M08`에 채널 혼잡도만 있고 **연결 주파수 대역(`2.4/5GHz`)·채널 번호(`Ch.36` 등)·대역폭(`20/40/80MHz`)**이 누락되었으며, ③ 직관적인 **링크 종합 품질 지수(`Link Quality %`)**가 분리되어 있지 않았음. 또한 각 항목의 **의미, 문제가 발생하는 상황, 사전 감지 방법, 사후 분석 방법**을 섞이지 않게 독립적으로 표현할 필요가 있음.
- **근본 원인**: 초기 지표 설계 시 단일 안테나(SISO) 기준의 통합 RSSI와 채널 사용률(%) 중심으로만 구성하여 다중 안테나(MIMO) 불균형 및 대역 강등(Band Steering 실패) 시나리오를 별도 항목으로 분리하지 않았음.
- **해결 조치**:
  1. 기존 항목에 이질적인 단위를 섞는 대신 **독립 항목(`M19` MIMO 안테나별 신호 세기 및 편차, `M20` 무선 주파수 대역·채널 번호 및 대역폭, `M21` 무선 링크 종합 품질 지수)**으로 분리 추가하여 총 **21종(`M01`~`M21`, 전수 `AGV/AMR` 및 `ACS` 전용)** 체계로 확장함.
  2. 21종 전 항목의 `analysis_usage`에 `problem_scenario`(`[문제가 발생할 수 있는 현장 상황]`), `pre_detection`(`[문제 발생 전 사전 감지 방법]`), `post_mortem`(`[문제 발생 후 사후 분석 방법]`)을 구조화하고 백과사전 탭 상세 인스펙터와 카드 목록에 명확히 분리 렌더링함.
- **재발 방지 대책**: `tests/test_api.py`에서 21종(`M01`~`M21`) 전 항목의 `problem_scenario`, `pre_detection`, `post_mortem` 존재 여부 및 `MIMO`, `Chain`, `Channel`, `Link Quality` 키워드 포함 여부를 자동 검증하도록 테스트를 강화함.






