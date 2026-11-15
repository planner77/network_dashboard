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


