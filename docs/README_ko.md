<p align="center">
  <img src="assets/ghostshell-banner.svg" alt="GhostShell OS" width="600"/>
</p>

<h1 align="center">🧠 GhostShell OS (G.S.O.S.)</h1>

<p align="center">
  <em>"고스트는 논리이다. 데이터베이스는 껍질이다."</em>
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README_de.md">Deutsch</a> ·
  <a href="README_tr.md">Türkçe</a> ·
  <a href="README_zh.md">中文</a> ·
  <a href="README_ja.md">日本語</a> ·
  <a href="README_ko.md"><strong>한국어</strong></a> ·
  <a href="README_es.md">Español</a> ·
  <a href="README_fr.md">Français</a> ·
  <a href="README_ru.md">Русский</a> ·
  <a href="README_pt.md">Português</a> ·
  <a href="README_ar.md">العربية</a> ·
  <a href="README_hi.md">हिन्दी</a>
</p>

---

## 🌊 GhostShell이란?

**GhostShell은 관계형 AI 운영체제입니다.** OpenClaw 같은 프로젝트가 시스템 *위에서* 실행되는 반면, GhostShell은 시스템 **그 자체**입니다. PostgreSQL 데이터베이스를 하드웨어 드라이버, 파일 시스템, AI 모델("고스트")이 SQL 테이블을 통해 통신하는 살아있는 유기체로 변환합니다.

모든 생각. 모든 파일 이동. 모든 하드웨어 신호. 이 모든 것이 — ACID 호환 데이터베이스 트랜잭션. 파괴 불가능. 안전. 일관적.

---

## 🔥 왜 OpenClaw가 아니라 GhostShell인가?

| | OpenClaw | GhostShell OS |
|---|---|---|
| **아키텍처** | 시스템 위의 애플리케이션 | 시스템 **그 자체** |
| **데이터 영속성** | 휘발성 메모리 | ACID 트랜잭션 — 모든 생각이 영구적 |
| **하드웨어** | 외부 API | 테이블로서의 하드웨어 — `UPDATE cpu SET governor='performance'` |
| **AI 모델** | 단일 모델, 재시작 필요 | 핫스왑 고스트 — 컨텍스트 손실 없이 LLM 교체 |
| **보안** | 애플리케이션 수준 | 3계층 불변성: 코어 → 런타임 → 고스트 |
| **자가 복구** | 수동 | 인간 승인이 포함된 자율 복구 파이프라인 |

---

## 🔒 세 가지 보안 계층

**고스트는 복구할 수 있다 — 하지만 재구축은 절대 할 수 없다.** 모든 제안된 변경은 다음을 거칩니다:

```
고스트 제안 → 인간 승인 → SECURITY DEFINER 실행 → 감사 로그
```

---

## 🦾 기능

- [x] **테이블로서의 하드웨어** — `SQL UPDATE`로 팬, CPU 클럭, 드라이브를 제어
- [x] **17개 데스크톱 앱** — 고스트 채팅, 소프트웨어 스토어, LLM 관리자 등
- [x] **핫스왑 고스트** — 컨텍스트 손실 없이 런타임에서 LLM 교체
- [x] **불변성 보호** — 176개 스키마 핑거프린트, 위반 로깅
- [x] **복구 파이프라인** — 고스트 제안 → 인간 승인 → 안전한 실행
- [x] **OpenClaw 브리지** — OpenClaw 스킬을 더 안전한 환경으로 가져오기
- [x] **실시간 메트릭** — CPU, RAM, GPU, 온도를 WebSocket으로 스트리밍
- [x] **행 수준 보안** — 5개 데이터베이스 역할에 걸친 71개 RLS 정책 테이블
- [ ] **자율 코딩** *(진행 중)* — 고스트가 자체 SQL 마이그레이션 작성
- [ ] **비전 통합** *(계획 중)* — `media_metadata`에서 실시간 비디오 분석
- [ ] **분산 고스트** *(계획 중)* — 노드 간 다중 고스트 인스턴스

---

<p align="center">
  <strong>GhostShell OS</strong> — 모든 생각이 트랜잭션이 되는 곳.<br/>
  <em>Repair-Lab · 2026</em>
</p>
