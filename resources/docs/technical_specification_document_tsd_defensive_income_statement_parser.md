# Technical Specification Document (TSD)

**Project:** Defensive Income Statement Parser  \
**Version:** 1.2  \
**Status:** Engineering Draft  \
**Date:** 18 December 2025

---

## 1. Purpose of This Document

This Technical Specification Document (TSD) defines **how the functional requirements described in the FSD are implemented**. It is intended for:
- Software engineers
- Platform and infrastructure teams
- Technical reviewers

This document MUST remain aligned to the FSD but MAY evolve independently as implementation details change.

---

## 2. Design Philosophy

- PDFs are treated as hostile, semi-graphical artefacts
- Deterministic parsing is preferred but never trusted blindly
- Vision-based parsing is used as a controlled fallback
- Failure states must be explicit and observable

---

## 3. Technology Stack

- **Language:** Python 3.11+
- **PDF Processing:** PyMuPDF
- **Vision Parsing:** Docling
- **Validation:** Pandas, Pydantic
- **Async Processing:** Celery + Redis
- **Persistence:** PostgreSQL + S3-compatible object storage

---

## 4. Core Components

### 4.1 Ingestion Guard
- Text layer integrity checks
- Coordinate normalisation
- Entropy scoring

### 4.2 Routing Engine
- Template fingerprint matching
- Threshold-based parser selection

### 4.3 Deterministic Parser
- Span merging (kerning correction)
- Vector-based semantic inference
- Stateful pagination handling
- Explicit abort semantics

### 4.4 Vision Parser Integration
- External vision engine invocation
- Output normalisation layer
- Confidence and warning propagation

### 4.5 Validation Engine
- Arithmetic consistency checks
- Semantic validation

### 4.6 Human Review Interface
- Bounding box overlays
- Field-level correction support
- Audit logging

---

## 5. Failure Modes & Abort Semantics

Deterministic parsing SHALL abort on:
- Missing or ambiguous headers
- Multiple conflicting totals
- Pagination loops
- Structural inconsistency

Abort SHALL trigger vision fallback and HITL review.

---

## 6. Data Model (Technical)

Supports:
- Maker–checker workflow
- Versioned extraction results
- Audit traceability

---

## 7. Test Strategy

- Unit tests per heuristic
- Integration tests per parsing path
- Regression tests on golden documents

---

## 8. Alignment to FSD (Traceability)

| FSD Requirement | TSD Implementation |
|-----------------|--------------------|
| Hybrid parsing | Routing + parsers |
| Validation | MathAudit |
| HITL | Review service |
| Auditability | Versioned schema & logs |

---

## 9. Non-Scope (Technical)

- Model training
- Financial interpretation
- Ledger integration

---

**End of Technical Specification Document**

