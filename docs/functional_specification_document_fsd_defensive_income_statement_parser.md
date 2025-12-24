# Functional Specification Document (FSD)

**Project:** Defensive Income Statement Parser (Maker–Checker)  \
**Version:** 1.2  \
**Status:** Draft for Architecture / Risk Review  \
**Date:** 18 December 2025

---

## 1. Purpose of This Document

This Functional Specification Document (FSD) defines **what the system must do and why**, independent of implementation choices. It is intended for:
- Architecture Review Boards
- Risk & Compliance stakeholders
- Product owners and delivery managers

Technical implementation details are intentionally abstracted and delegated to the Technical Specification Document (TSD).

---

## 2. Business Problem Statement

Financial income statements are commonly delivered as semi-structured PDFs that exhibit:
- Inconsistent layouts
- Corrupted or misleading text layers
- Visual semantics (e.g. totals defined by lines rather than metadata)

Manual processing is slow, error-prone, and operationally expensive. Fully autonomous automation introduces unacceptable risk in regulated environments.

---

## 3. System Objectives

- Extract structured income statement data with high accuracy
- Explicitly detect and manage document parsing risk
- Minimise manual effort via confidence-based automation
- Ensure full auditability and human override (maker–checker)

---

## 4. Scope Definition

### 4.1 In Scope
- PDF ingestion and validation
- Hybrid document parsing (deterministic + vision)
- Automated validation of extracted values
- Human-in-the-loop review and approval
- API handoff of approved data

### 4.2 Out of Scope
- Mobile applications
- Accounting advice or interpretation
- Direct posting into financial ledgers
- Model training or optimisation

---

## 5. Architectural Principles

1. **Defensive by Default** – Assume documents may be misleading or malformed
2. **Fail Transparently** – Prefer explicit failure over silent errors
3. **Cost-Aware Automation** – Use expensive parsing only when required
4. **Human Authority** – Humans retain final approval rights

---

## 6. Functional Architecture Overview

The system follows a layered maker–checker architecture:

| Layer | Responsibility |
|------|----------------|
| Ingestion | File validation and normalisation |
| Routing | Risk-based parser selection |
| Extraction | Data capture from documents |
| Validation | Mathematical and semantic checks |
| Review | Human approval or correction |

---

## 7. Functional Requirements

### FR-1 Ingestion & Risk Assessment
- The system SHALL assess document integrity and text reliability
- High-risk documents SHALL be routed to more robust parsing paths

### FR-2 Hybrid Parsing
- The system SHALL support at least two extraction strategies:
  - Deterministic text-based parsing
  - Vision-based document understanding

### FR-3 Automated Validation
- Extracted data SHALL be validated for:
  - Arithmetic consistency
  - Mandatory field presence
  - Currency and date normalisation

### FR-4 Human-in-the-Loop Review
- Documents below confidence thresholds SHALL require human approval
- Review actions SHALL be auditable

### FR-5 Confidence-Based Decisioning
- The system SHALL compute a document-level confidence score
- Confidence SHALL govern auto-approval, review, or rejection

---

## 8. Phased Delivery Model

### Phase 1 – Proof of Concept (POC)
- Mandatory human review for all documents
- Limited document templates
- No auto-approval

### Phase 2 – Pilot
- Hybrid routing enabled
- Confidence-based review enforcement
- Initial cost controls

### Phase 3 – Production
- Auto-approval for high-confidence documents
- Template governance
- Full audit and monitoring

---

## 9. Risks (Functional View)

| Risk | Mitigation |
|-----|------------|
| Silent mis-extraction | Validation + HITL |
| Over-automation | Confidence gating |
| Reviewer overload | Auto-approval for low-risk cases |
| Regulatory non-compliance | Audit trails and controls |

---

## 10. Dependencies & References

- Document AI and PDF processing best practices
- Maker–Checker control patterns

---

**End of Functional Specification Document**