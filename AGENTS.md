# AGENTS.md — 프로젝트 운영 원칙 및 에이전트 업무 분장 지침

> **필수 준수 사항**: 모든 에이전트(코디네이터 및 서브에이전트/워커)는 작업을 시작하거나 단계를 전환할 때 **항상 본 `AGENTS.md`를 최우선으로 참조**해야 합니다.

---

## 1. 프로젝트 개요 및 핵심 목적

- **배경**: AGV/AMR이 현장 Wi-Fi를 통해 상위 시스템인 **ACS(AGV/AMR Control System)**와 연결되어 **30초 주기로 소켓(TCP) 상태 보고**를 수행하는 환경에서, 현장 무선 환경 악화·로밍 지연·채널 혼잡·통신 프로그램 응답 지연 등으로 연결 단절(보고/제어 불가)이 발생함.
- **목적**:
  1. 별도의 무선 인프라(AP/WLC) 장비 접근 권한 없이도 **오직 AGV/AMR과 ACS 양단에서 직접 수집 가능한 네트워크/시스템 상태 항목(18종)**을 조사 및 체계화.
  2. 기존 30초 보고 주기의 한계를 극복하는 **3단계 하이브리드 수집 모델**(① AGV 내부 1초 단위 임시 기록장 보관 + ② 평시 30초 정기 보고 시 요약 데이터 동봉 전송 + ③ 이상 징후 조기 알림 및 재연결 후 상세 기록 일괄 전송)을 수립하여 **사전 감지** 및 **사후 원인 분석**에 활용.
  3. **AGV/AMR 담당자**와 **ACS 담당자**가 각각 수행해야 할 개발·적용 과업을 명확히 정의.
  4. 일반 사용자와 현업 관계자가 쉽게 이해할 수 있는 평이한 용어와 **고시인성 인터랙티브 투어 가이드**가 포함된 Mock-up 사이트를 구축하고(실제 운영 시 **시계열 데이터베이스(TSDB) 도입의 필요성** 제시), `.env` 및 `docker-compose.yml` 기반으로 포트 **`9921`**에서 구동되도록 구성하여 GitHub 및 GHCR에 정식 배포.

---

## 2. 핵심 작성 및 구현 수칙 (Golden Rules)

1. **일반 사용자를 위한 쉬운 용어 사용 (전문 은어 자제)**
   - 개발자에게만 익숙한 외래어·은어 사용을 지양하고 누구나 직관적으로 이해할 수 있는 한국어 표현을 사용합니다:
     - `피기백(Piggyback)` → **30초 정기 보고 시 요약 데이터 동봉 전송 (함께 보내기)**
     - `1초 고주파 링버퍼(Ring Buffer)` → **AGV 내부 1초 단위 상시 기록장 (최근 5분 자동 덮어쓰기 블랙박스)**
     - `시나리오 주입(Fault Injection)` → **장애 상황 가상 체험 (시뮬레이션 실행)**
     - `내장 시계열 DB(Embedded TSDB)` 표현 지양 → **실제 운영 시 시계열 DB(Time-Series DB) 도입 필요성 및 시간대별 상태 이력 관리**로 표현
     - `소켓 행(Socket Hang)` → **통신 프로그램 일시 멈춤 (응답 지연)**
2. **수집 위치의 엄격한 한정 (`AGV/AMR` 및 `ACS` 전용)**
   - 현장 AP나 무선 컨트롤러(WLC) 장비에서 수집하는 항목은 제외하고, **오직 `AGV/AMR`과 `ACS`에서 직접 수집할 수 있는 항목만 포함**합니다.
3. **`.env` 기반 설정 관리 및 기본 포트 `9921`**
   - 접속 포트(`PORT=9921`, `DASHBOARD_PORT=9921`), 기본 테마(`DEFAULT_THEME=light`), 수집/보관 주기 등 모든 주요 설정값은 `.env`에서 관리하며 `docker-compose.yml`과 백엔드가 이를 읽어 동작하도록 합니다.
4. **`README.md` 상시 최신화**
   - `README.md`에는 프로젝트 설명, 용어 해설, `.env` 설정, 설치 및 실행 방법(`docker compose`), 그리고 진행 간 **변경 사항(Changelog)**을 기록하고 변경 발생 시마다 즉시 갱신합니다.

---

## 3. 프로젝트 진행 프로세스 (7단계 표준 파이프라인)

1. **분석 (Analysis)**: 요구사항 명확화, AGV/AMR 및 ACS 수집 가능 지표(18종) 정의, AGV/ACS 담당자별 업무 도출.
2. **설계 (Design)**: 시계열 데이터 스키마, 백엔드 시뮬레이터/API, 프론트엔드 라이트 기본 테마 UI/UX(`DESIGN.md`), 도커/환경변수 아키텍처 설계.
3. **구현 (Implementation)**: 백엔드 및 프론트엔드(5대 탭 + 고시인성 투어 가이드 + 고정 헤더 일람표 + 담당자별 역할 탭) 구현.
4. **로컬 테스트 (Local Test)**: `pytest` 자동화 검증, UI 레이아웃/투어 하이라이트 정렬 검증, `docker compose` 기반 `9921` 포트 기동 및 헬스체크 검증.
5. **실패 원장 기록 (Failure Ledger)**: 진행 과정에서 발생한 모든 시행착오, 레이아웃/시인성 이슈, 용어 개선, 환경 이슈를 `docs/FAILURE_LEDGER.md`에 즉시 기록.
6. **원격 푸시 (Remote Push)**: `.env`의 `remote_repo_url` 및 `remote_repo_token`을 활용하여 GitHub 원격 저장소(`main` 브랜치)에 푸시 (**`.env` 파일은 절대 커밋 금지**, `.env.example` 제공).
7. **정식 GHCR 게시 (GHCR Publish)**: `ghcr.io/planner77/network_dashboard:latest` 및 버전 태그로 도커 이미지를 게시하고 `docker compose up -d` 구동 확인.

---

## 4. 사용 가능한 모델 기반 에이전트별 업무 분장 (Model & Role Assignment)

| 에이전트 역할 (Role) | 지정 모델 (Model ID / Display Name) | 핵심 담당 업무 및 책임 범위 |
| :--- | :--- | :--- |
| **총괄 아키텍트 & 코디네이터** | `gemini-4-argon-medium` | 요구사항 명확화, 전체 아키텍처 조율, 통합 검증, Git 원격 푸시 및 GHCR 정식 배포 총괄 |
| **네트워크 도메인 & 데이터 분석가** | `gemini-4-argon-medium` / `claude-opus-5-5-high` | AGV/AMR 및 ACS 전용 18종 수집 지표 명세화, 쉬운 용어 해설, AGV/ACS 담당자별 과업 정리, 사전 감지·사후 분석 시나리오 설계 |
| **시계열 데이터 & 백엔드 엔지니어** | `gemini-4-argon-medium` / `claude-sonnet-5-5-high` | `.env` 설정 로더(포트 `9921`), 시계열 데이터 저장소 및 실시간 시뮬레이터, FastAPI 서버 구축 |
| **프론트엔드 & 시각화 엔지니어** | `gemini-4-argon-high` | `DESIGN.md` 기반 라이트(기본)/다크 테마 UI, 겹침 없는 2단 헤더, 고시인성 투어 가이드, 고정 헤더 일람표, AGV/ACS 담당자 역할 탭 구현 |
| **QA 검증 & 데브옵스 엔지니어** | `gemini-3.8-flash-high` | `docker-compose.yml`(`9921` 포트 & `.env` 연동), `Dockerfile`, `README.md`(변경 이력 포함), `tests/test_api.py` 및 배포 검증 |

---

## 5. 상황별 참조 마크다운 라우팅 테이블 (Document Routing Guide)

| 작업 상황 (When / Context) | 참조해야 할 문서 경로 (Target Markdown) | 문서 핵심 내용 요약 |
| :--- | :--- | :--- |
| **모든 작업 시작 전 / 단계 전환 시 / 에이전트 할당 시** | [`AGENTS.md`](file:///home/planner/Dev/network_dashboard/AGENTS.md) | 7단계 진행 원칙, 쉬운 용어 수칙, `.env`(`9921` 포트) 관리 원칙, 문서 라우팅 규칙 |
| **화면 레이아웃, 색상, 라이트 기본 테마, 투어 시인성, 테이블 고정 헤더 등 UI/UX 작업 시** | [`DESIGN.md`](file:///home/planner/Dev/network_dashboard/DESIGN.md) | Light Enterprise 기본 테마, 2단 헤더 레이아웃, 고시인성 투어 스포트라이트, Sticky 테이블 헤더 규칙 |
| **AGV/AMR 및 ACS 수집 지표 작성, 사전 감지/사후 분석, 담당자별 할 일 정리 시** | [`docs/ANALYSIS_AND_METRICS.md`](file:///home/planner/Dev/network_dashboard/docs/ANALYSIS_AND_METRICS.md) | AGV/ACS 전용 18종 수집 지표 상세 명세, 쉬운 용어 정의, 4대 장애 시나리오, AGV/ACS 담당자별 업무 분담 |
| **시계열 DB 필요성 설명, API 엔드포인트, `.env` 및 `docker-compose.yml` 구성 시** | [`docs/ARCHITECTURE.md`](file:///home/planner/Dev/network_dashboard/docs/ARCHITECTURE.md) | 시계열 DB 도입 필요성 및 구조, `.env` 환경변수 명세, REST API 명세, 5대 탭 구조 |
| **프로젝트 소개, 설치/실행 안내, 버전별 변경 사항(Changelog) 갱신 시** | [`README.md`](file:///home/planner/Dev/network_dashboard/README.md) | 프로젝트 개요, 핵심 용어 해설, `.env` 및 `docker compose` 실행 가이드(포트 `9921`), 변경 이력 |
| **오류/버그 발생 시, UI/UX 결함 수정 시, 원격 푸시/GHCR 배포 전후 점검 시** | [`docs/FAILURE_LEDGER.md`](file:///home/planner/Dev/network_dashboard/docs/FAILURE_LEDGER.md) | 단계별 실패 원장(발생 일시, 단계, 현상, 근본 원인, 해결 조치, 재발 방지 대책) 기록 및 조회 |
