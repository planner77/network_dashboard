# AGENTS.md — 프로젝트 운영 원칙 및 에이전트 업무 분장 지침

> **필수 준수 사항**: 모든 에이전트(코디네이터 및 서브에이전트/워커)는 작업을 시작하거나 단계를 전환할 때 **항상 본 `AGENTS.md`를 최우선으로 참조**해야 합니다.

---

## 1. 프로젝트 개요 및 핵심 목적

- **배경**: AGV/AMR이 현장 Wi-Fi를 통해 상위 시스템인 **ACS(AGV/AMR Control System)**와 연결되어 **30초 주기로 소켓(TCP) 상태 보고**를 수행하는 환경에서, 현장 무선 환경 악화·로밍 지연·채널 혼잡·소켓 블로킹 등으로 연결 단절(보고/제어 불가)이 발생함.
- **목적**:
  1. AGV/AMR, 무선 인프라(AP/WLC), ACS에서 수집 가능한 네트워크/시스템 상태 지표를 전수 조사 및 체계화.
  2. 기존 30초 보고 주기의 한계를 극복하는 **하이브리드 수집 아키텍처**(로컬 1~5초 고주파 링버퍼 + 30초 요약 피기백 + 이상 징후 조기 경보 + 재연결 후 블랙박스 덤프)를 수립하여 **사전 감지(Pre-detection)** 및 **사후 원인 분석(Post-mortem RCA)**에 활용.
  3. 이해관계자 및 엔지니어에게 직관적으로 설명·시연하기 위한 **인터랙티브 투어 가이드 내장형 Live Mock-up 사이트**를 시계열 DB(TSDB) 기반으로 구축하고 단일 도커 이미지(All-in-One) 및 GHCR로 정식 배포.

---

## 2. 프로젝트 진행 프로세스 (7단계 표준 파이프라인)

1인 개발/단일 리포지토리 특성상 PR이나 외부 CI 파이프라인을 거치지 않으며, 아래 **7단계 절차**를 엄격히 준수하여 진행합니다.

1. **분석 (Analysis)**: 요구사항 명확화, 30초 보고 주기의 불합리성 합리화, 수집 지표(L1~L7) 및 장애 시나리오 4종 정의.
2. **설계 (Design)**: 시계열 DB 스키마, 백엔드 실시간 시뮬레이터/API, 프론트엔드 UI/UX(`DESIGN.md`), 도커 패키징 아키텍처 설계.
3. **구현 (Implementation)**: 에이전트 업무 분장에 따라 백엔드(TSDB 엔진 + 시뮬레이터 + API) 및 프론트엔드(관제 대시보드 + 2D 맵/히트맵 + 사전감지/사후분석 랩 + 수집 항목 백과사전 + 인터랙티브 투어 가이드) 구현.
4. **로컬 테스트 (Local Test)**: 단위/통합 검증, UI 렌더링 및 투어 가이드 동작 검증, Docker 이미지 로컬 빌드 및 컨테이너 기동 후 헬스체크/API 응답 테스트.
5. **실패 원장 기록 (Failure Ledger)**: 진행 과정에서 발생한 모든 시행착오, 빌드/런타임 오류, 설계 변경, 환경 이슈를 `docs/FAILURE_LEDGER.md`에 원인·해결책·재발방지책과 함께 즉시 기록.
6. **원격 푸시 (Remote Push)**: `.env`의 `remote_repo_url` 및 `remote_repo_token`을 활용하여 GitHub 원격 저장소(`main` 브랜치)에 코드 및 문서 푸시 (**주의: `.env` 파일 및 토큰 값은 절대 커밋 금지**).
7. **정식 GHCR 게시 (GHCR Publish)**: `.env`의 인증 정보를 사용해 GitHub Container Registry(`ghcr.io/planner77/network_dashboard:latest` 및 버전 태그)에 정식 도커 이미지를 푸시하고 배포 검증.

---

## 3. 사용 가능한 모델 기반 에이전트별 업무 분장 (Model & Role Assignment)

현재 환경에서 사용 가능한 모델 목록(`swarm models` 조회 기준)의 추론 깊이·속도·특성에 맞춰 다음과 같이 에이전트 역할과 담당 모델을 분장합니다.

| 에이전트 역할 (Role) | 지정 모델 (Model ID / Display Name) | 핵심 담당 업무 및 책임 범위 |
| :--- | :--- | :--- |
| **총괄 아키텍트 & 코디네이터**<br>*(Coordinator / Lead Architect)* | `gemini-4-argon-medium`<br>*(Gemini 4 Argon Medium — 현재 세션 기본 모델)* | 요구사항 명확화, 전체 시스템 아키텍처 조율, 에이전트 작업 지시 및 통합 검증, Git 원격 푸시 및 GHCR 정식 배포 총괄 |
| **네트워크 도메인 & 데이터 분석가**<br>*(Domain & Telemetry Analyst)* | `claude-opus-5-5-high` 또는 `gemini-4-hydrogen-high`<br>*(고난도 도메인 추론 및 알고리즘 설계)* | Wi-Fi(802.11k/v/r)/TCP/ACS 계층별 수집 지표 명세 수립, 사전 감지(EWMA/위험도 스코어링) 및 사후 원인 분석(4대 장애 시나리오 의사결정 트리) 알고리즘 설계 |
| **시계열 DB & 백엔드 엔지니어**<br>*(TSDB & Backend Engineer)* | `claude-sonnet-5-5-high` 또는 `gemini-4-argon-high`<br>*(백엔드/DB 엔지니어링 특화)* | 내장형 시계열 DB(SQLite WAL TSDB) 스키마 및 쿼리 엔진 구현, 실시간 데이터 스트리밍 시뮬레이터(1초/30초 주기 + 4대 시나리오 재현) 및 FastAPI/Express REST·SSE 서버 구축 |
| **프론트엔드 & 시각화 엔지니어**<br>*(Frontend & Data Viz Engineer)* | `claude-sonnet-5-5-high` 또는 `gemini-4-argon-high`<br>*(UI/UX 및 인터랙티브 차트 구현 특화)* | `DESIGN.md` 기반 다크/라이트 관제 UI 구현, 실시간 시계열 차트, 공장 2D Floor Plan & AP 음영 히트맵, 수집 항목 상세 카탈로그 페이지, 인터랙티브 투어 가이드 구현 |
| **QA 검증 & 데브옵스 엔지니어**<br>*(QA Verifier & DevOps Engineer)* | `gemini-3.8-flash-high`<br>*(빠른 검증, 테스트 자동화 및 패키징)* | 로컬 빌드/런타임 테스트, API 및 UI 정합성 검증, 멀티스테이지 `Dockerfile` 및 `docker-compose.yml` 작성, `docs/FAILURE_LEDGER.md` 기록 점검, GHCR 배포 테스트 |

> **모델 운용 규칙**: 서브에이전트(`invoke_subagent`) 또는 스웜 워커(`swarm`) 호출 시 작업 복잡도에 맞춰 기본 상속(`inherit`) 또는 위 표의 최적 모델을 배치하며, 쿼터 소진 시 즉시 대체 모델로 전환하고 실패 원장에 기록합니다.

---

## 4. 상황별 참조 마크다운 라우팅 테이블 (Document Routing Guide)

프로젝트 진행 중 특정 작업 상황에 진입할 때 **반드시 아래 표에 명시된 마크다운 문서를 먼저 읽고 작업**해야 합니다.

| 작업 상황 (When / Context) | 참조해야 할 문서 경로 (Target Markdown) | 문서 핵심 내용 요약 |
| :--- | :--- | :--- |
| **모든 작업 시작 전 / 단계 전환 시 / 에이전트 할당 시** | [`AGENTS.md`](file:///home/planner/Dev/network_dashboard/AGENTS.md) | 7단계 진행 원칙, 모델별 에이전트 업무 분장, 보안 규칙(`.env` 보호), 문서 라우팅 규칙 |
| **화면 레이아웃, 색상, 폰트, 차트, 다크/라이트 테마 등 UI/UX 설계 및 프론트엔드 구현 시** | [`DESIGN.md`](file:///home/planner/Dev/network_dashboard/DESIGN.md) | 전문가용 관제 시스템 컬러 시스템(다크/라이트), 타이포그래피 위계, 수직·수평 정렬 그리드 규칙, 차트 및 투어 가이드 UI 표준 |
| **수집 지표 카탈로그 작성, 시뮬레이션 데이터 생성, 사전 감지/사후 분석 로직 및 차트 구성 시** | [`docs/ANALYSIS_AND_METRICS.md`](file:///home/planner/Dev/network_dashboard/docs/ANALYSIS_AND_METRICS.md) | 30초 보고 한계 극복 하이브리드 수집 모델, L1~L7 18개 수집 지표 상세 명세(단위/위치/주기/부하/방법/분석법), 4대 장애 시나리오 및 분석 알고리즘 |
| **시계열 DB 스키마 구현, API 엔드포인트 개발, 프론트-백엔드 연동, Docker/GHCR 패키징 시** | [`docs/ARCHITECTURE.md`](file:///home/planner/Dev/network_dashboard/docs/ARCHITECTURE.md) | All-in-One 컨테이너 아키텍처, TSDB 테이블/인덱스 구조, REST/SSE API 명세, 디렉토리 구조, GHCR 배포 절차 |
| **오류/버그 발생 시, 빌드/테스트 실패 시, 원격 푸시/GHCR 배포 전후 점검 시** | [`docs/FAILURE_LEDGER.md`](file:///home/planner/Dev/network_dashboard/docs/FAILURE_LEDGER.md) | 단계별 실패 원장(발생 일시, 단계, 현상, 근본 원인, 해결 조치, 재발 방지 대책) 기록 및 조회 |

---

## 5. 보안 및 형상 관리 필수 수칙

1. **`.env` 파일 절대 커밋 금지**: `.env`에는 `remote_repo_url`과 `remote_repo_token`(GitHub PAT)이 포함되어 있으므로 `.gitignore`에 등록하여 원격 저장소나 도커 이미지 레이어에 절대 포함되지 않도록 합니다.
2. **원격 푸시 및 GHCR 인증**:
   - Git Push 시 `.env`의 토큰을 일시적 인증 헤더 또는 credential helper로만 사용하며, `.git/config`에 평문 토큰이 남지 않도록 관리하거나 컨테이너 빌드 컨텍스트(`.dockerignore`)에서 `.env`와 `.git`을 제외합니다.
3. **실패 원장 투명성**: 사소한 빌드 에러나 의존성 충돌이라도 숨기지 않고 `docs/FAILURE_LEDGER.md`에 기록하여 지식으로 자산화합니다.
