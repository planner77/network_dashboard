# DESIGN.md — AGV/AMR 네트워크 인텔리전스 관제 UI/UX 디자인 시스템

> **참조 원칙**: 프론트엔드 레이아웃, 컴포넌트, 차트, 투어 가이드, 테마 스타일링 작업을 수행할 때는 **항상 본 `DESIGN.md`의 규칙을 준수**해야 합니다.

---

## 1. 디자인 철학 (Design Philosophy)

1. **전문가적 차분함 (Calm Industrial Precision)**
   - 스마트 팩토리 및 AGV/AMR 관제 엔지니어가 장시간 모니터링해도 눈의 피로가 없도록 **저채도 슬레이트(Desaturated Slate/Navy) 기반의 차분한 배경**과 정제된 보더(Border)를 사용합니다.
   - 원색(순수 빨강 `#FF0000`, 순수 초록 `#00FF00` 등) 사용을 금지하고, **신뢰감 있는 세련된 시맨틱 컬러**(Teal, Amber, Coral Red, Indigo Blue)를 사용합니다.
2. **엄격한 수직·수평 정렬과 균형감 (Strict Grid & Alignment)**
   - 모든 카드, 테이블, KPI 위젯, 차트 패널은 **12-Column CSS Grid**와 **8px 기본 공간 단위(4px 보조 단위)**에 맞춰 수직·수평 기준선(Baseline & Edge)이 정확히 일치해야 합니다.
   - 같은 행(Row)에 배치된 카드들은 동일한 높이(`align-items: stretch`)와 동일한 헤더 높이, 내부 패딩을 유지합니다.
3. **명확한 시각적 위계와 차등 강조 (Visual Hierarchy & Emphasis)**
   - 내용의 중요도에 따라 **폰트 크기(Size), 굵기(Weight), 색상 명도(Contrast), 배경 배지(Badge)**를 체계적으로 차등 적용합니다.
   - 숫자와 시계열 지표는 값 변화 시 레이아웃이 흔들리지 않도록 반드시 `font-variant-numeric: tabular-nums` 및 고정폭(Monospace) 폰트를 적용합니다.

---

## 2. 컬러 시스템 (Dual Theme: Dark Slate 기본 + Light Enterprise 전환 지원)

CSS 변수(`:root` 및 `[data-theme="light"]`)를 통해 다크/라이트 테마 즉시 전환을 지원합니다.

### 2.1 기본 테마: Dark Slate Mission Control (`[data-theme="dark"]`)
| 토큰 역할 | CSS 변수명 | 색상 코드 (HEX) | 용도 설명 |
| :--- | :--- | :--- | :--- |
| **앱 최하단 배경** | `--bg-canvas` | `#0B0F17` | 전체 화면 베이스 배경 (깊고 차분한 다크 네이비 슬레이트) |
| **카드/패널 배경** | `--bg-surface` | `#111827` | 대시보드 카드, 차트 컨테이너, 사이드바 배경 |
| **강조/호버 패널** | `--bg-elevated` | `#1E293B` | 테이블 헤더, 선택된 행, 툴팁, 모달, 투어 팝오버 배경 |
| **기본 보더** | `--border-subtle` | `#1F2937` | 카드 외곽선 및 내부 구분선 (1px solid) |
| **강조 보더** | `--border-focus` | `#334155` | 활성 카드, 호버 상태, 입력창 포커스 보더 |
| **1차 텍스트 (제목/핵심값)** | `--text-primary` | `#F8FAFC` | 페이지 타이틀, 섹션 제목, KPI 핵심 수치 (**Bold 600~700**) |
| **2차 텍스트 (본문/설명)** | `--text-secondary` | `#94A3B8` | 일반 본문, 테이블 셀 텍스트, 차트 축 레이블 (Regular 400~500) |
| **3차 텍스트 (보조/단위)** | `--text-muted` | `#64748B` | 단위(`dBm`, `ms`, `%`), 타임스탬프 보조 표기, 비활성 캡션 |

### 2.2 전환 테마: Light Enterprise (`[data-theme="light"]`)
| 토큰 역할 | CSS 변수명 | 색상 코드 (HEX) | 용도 설명 |
| :--- | :--- | :--- | :--- |
| **앱 최하단 배경** | `--bg-canvas` | `#F1F5F9` | 눈부심을抑제한 쿨그레이 엔터프라이즈 배경 |
| **카드/패널 배경** | `--bg-surface` | `#FFFFFF` | 깔끔한 화이트 카드 표면 |
| **강조/호버 패널** | `--bg-elevated` | `#F8FAFC` | 테이블 헤더, 보조 요약 박스 배경 |
| **기본 보더** | `--border-subtle` | `#E2E8F0` | 정돈된 1px 카드 및 테이블 구분선 |
| **강조 보더** | `--border-focus` | `#CBD5E1` | 호버 및 포커스 상태 외곽선 |
| **1차 텍스트 (제목/핵심값)** | `--text-primary` | `#0F172A` | 고대비 딥 슬레이트 타이틀 및 핵심 값 |
| **2차 텍스트 (본문/설명)** | `--text-secondary` | `#475569` | 차분한 미디엄 슬레이트 본문 텍스트 |
| **3차 텍스트 (보조/단위)** | `--text-muted` | `#64748B` | 단위 및 부가 메타데이터 텍스트 |

### 2.3 시맨틱 상태 및 강조 컬러 (Semantic & Accent Palette)
| 상태 / 의미 | CSS 변수명 | Dark 테마 HEX | Light 테마 HEX | 사용 원칙 |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Brand (주요 강조)** | `--accent-primary` | `#38BDF8` (Sky Cyan) | `#0284C7` (Deep Sky) | 활성 탭, 핵심 링크, 선택된 AGV 포커스, 주요 액션 버튼 |
| **Secondary (분석/AI 예측)** | `--accent-indigo` | `#818CF8` (Soft Indigo) | `#4F46E5` (Indigo) | 사전 감지(Pre-detection) 예측선, 이상 징후 스코어 차트 |
| **Normal / Healthy (정상)** | `--status-ok` | `#10B981` (Emerald) | `#059669` (Emerald) | 연결 정상(Connected), 양호한 RSSI(-65dBm 이상), 정상 보고 |
| **Warning / Pre-detect (사전 감지 경보)** | `--status-warn` | `#F59E0B` (Amber) | `#D97706` (Amber) | **사전 감지 구간(Pre-Disconnect Warning)**, 로밍 지연, 재전송 증가 |
| **Critical / Disconnected (단절/장애)** | `--status-crit` | `#F43F5E` (Rose Coral) | `#E11D48` (Rose Red) | **소켓 연결 끊김(30s Timeout)**, 음영지역 단절, 패킷 유실 임계 초과 |

---

## 3. 타이포그래피 및 콘텐츠 차등 위계 (Typography & Hierarchy)

- **기본 UI 산세리프 폰트**: `'Inter', 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif`
- **수치/코드/지표 고정폭 폰트**: `'JetBrains Mono', 'Fira Code', monospace` (`font-variant-numeric: tabular-nums`)

### 계층별 스타일 차등 규칙
| 위계 단계 | 크기 (Font Size) | 굵기 (Weight) | 색상 토큰 | 적용 대상 및 강조 방식 |
| :--- | :--- | :--- | :--- | :--- |
| **H1 (화면 대제목)** | `1.375rem` (22px) | `700 (Bold)` | `--text-primary` | 상단 헤더 타이틀, 페이지 주 제목 (`letter-spacing: -0.02em`) |
| **H2 (섹션/패널 제목)** | `1.0rem` (16px) | `600 (SemiBold)` | `--text-primary` | 카드 상단 타이틀, 분석 섹션 헤더 (좌측에 컬러 인디케이터 바 또는 아이콘 동반) |
| **H3 (서브그룹/항목명)** | `0.875rem` (14px) | `600 (SemiBold)` | `--text-primary` | 수집 지표명(예: `RSSI`, `TCP Retransmission`), 시나리오 카드 타이틀 |
| **KPI Hero Value (핵심 수치)** | `1.75rem` (28px) | `700 (Bold)` | 상태별 시맨틱 컬러 | 상단 요약 카드의 핵심 수치 (고정폭 폰트 + 우측 하단에 `0.75rem` `--text-muted` 단위 병기) |
| **Body (본문/설명)** | `0.875rem` (14px) | `400 (Regular)` | `--text-secondary` | 지표 설명, 분석 리포트 본문 (`line-height: 1.6`) |
| **Body Emphasis (본문 내 강조)** | `0.875rem` (14px) | `600 (SemiBold)` | `--text-primary` 또는 `--accent-primary` | 본문 내 핵심 임계치(예: **`-75 dBm 이하`**), 중요 원인 키워드 볼드+색상 차등 |
| **Caption / Meta (보조/단위/주기)** | `0.75rem` (12px) | `500 (Medium)` | `--text-muted` | 테이블 헤더, 차트 축, 수집 주기(`1s`, `30s`), 타임스탬프 |

---

## 4. 화면 레이아웃 및 수직·수평 정렬 표준 (Layout & Alignment Rules)

1. **전체 앱 프레임 구조 (App Shell)**
   - **상단 글로벌 내비게이션 바 (높이 `60px` 고정)**:
     - 좌측: 시스템 로고 + 타이틀 (`AGV/AMR Network Telemetry & RCA Center`) + 실시간 시계열 DB 스트리밍 상태 배지(`LIVE TSDB • 1s/30s Stream`)
     - 중앙: 4개 핵심 뷰 전환 탭 (수평 중앙 정렬 및 하단 액티브 인디케이터 바)
       1. `실시간 관제 & 맵 (Live Fleet & 2D Map)`
       2. `사전 감지 & 사후 분석 랩 (Pre-Detection & RCA Lab)`
       3. `수집 항목 백과사전 (Telemetry Metrics Spec)`
       4. `시스템 아키텍처 & 수집 모델 (Hybrid Architecture)`
     - 우측: `[가이드 투어 시작 (Tour Guide)]` 강조 버튼, 시나리오 주입 셀렉터, 다크/라이트 테마 전환 버튼 (`수직 중앙 정렬 align-items: center`).
2. **그리드 및 정렬 원칙**
   - 컨테이너 최대 폭: `1600px` (와이드 모니터 최적화, 좌우 패딩 `24px`, 중앙 정렬).
   - 그리드 간격(Gap): 기본 `16px` (`1rem`), 카드 내부 패딩: `20px` (`1.25rem`).
   - **수평 정렬 규칙**:
     - 동일 행(Row)에 위치한 모든 카드(예: 상단 4개 KPI 요약 카드)는 상단 모서리와 하단 모서리가 1px의 오차 없이 수평 일직선상에 놓여야 합니다.
     - 카드 헤더는 항상 `display: flex; justify-content: space-between; align-items: center; height: 28px; margin-bottom: 12px;`로 통일합니다.
   - **수직 정렬 규칙**:
     - 좌우 분할 레이아웃(예: 좌측 8컬럼 차트 + 우측 4컬럼 진단 패널)에서 좌우 컬럼의 외곽 좌/우 라인은 상단 KPI 그리드의 좌/우 외곽 라인과 정확히 수직 정렬되어야 합니다.
     - 데이터 테이블에서 **텍스트 컬럼은 좌측 정렬(`text-align: left`)**, **수치/단위/점수 컬럼은 우측 정렬(`text-align: right`)**, **상태 배지/주기/수집위치 컬럼은 중앙 정렬(`text-align: center`)**로 통일합니다.

---

## 5. 데이터 시각화 및 투어 가이드 UX 표준

1. **다중 계층 동기화 차트 (Synchronized Multi-Layer Time-Series Charts)**
   - 사전 감지 및 사후 분석 화면에서는 X축(시간축)이 수직으로 완벽히 정렬된 3단 시계열 차트를 배치합니다:
     - **Layer 1 (무선 물리/MAC 계층)**: `RSSI (dBm)`, `SNR (dB)`, `Channel Utilization (%)` + 로밍 이벤트 마커
     - **Layer 2 (네트워크/전송 계층)**: `Gateway Ping RTT (ms)`, `TCP Retransmits (count/s)`, `Socket Send-Q (bytes)`
     - **Layer 3 (통합 위험도 & 30초 보고 상태)**: `Pre-Detection Anomaly Score (0~100)` + **사전 감지 경보 시점(T-18s Amber 수직선)** vs **30초 소켓 단절 발생 시점(T-0s Red 수직선 & 음영 구간)** 비교 시각화.
2. **2D 스마트 팩토리 맵 & AP 음영 히트맵**
   - 공장 레이아웃 위에 AP 4기(`AP-Zone-A` ~ `AP-Zone-D`)의 신호 커버리지 반경과 전파 음영/간섭 구역(Dead Zone / Interference Zone)을 시각적으로 표시하고, AGV 6대의 실시간 이동 위치와 궤적 색상을 네트워크 품질(정상=Emerald, 사전감지=Amber, 단절=Rose)로 렌더링합니다.
3. **인터랙티브 투어 가이드 (Interactive Spotlight Tour Guide)**
   - 최초 접속 시 환영 배너 또는 상단 `[가이드 투어 시작]` 버튼을 통해 언제든 실행 가능한 **단계별 스포트라이트 투어(Step-by-Step Guided Tour)**를 제공합니다.
   - 각 투어 스텝은 해당 화면이나 카드를 자동으로 활성화(탭 자동 전환 포함)하고, 대상 영역을 하이라이트한 뒤 **발표자용 핵심 설명 포인트(배경 → 문제점 → 수집 지표 → 사전 감지 원리 → 사후 원인 분석 결과)**를 깔끔한 팝오버 카드로 안내합니다.
