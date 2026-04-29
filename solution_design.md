# Solution Design: Kubernetes Resource Optimization Agent (AIRIS)
**Version:** 0.4 — Draft  
**Date:** April 10, 2026  
**Status:** In Review

---

## Table of Contents

1. [Overview](#1-overview)
2. [Problem Statement](#2-problem-statement)
3. [Proposed Solution](#3-proposed-solution)
4. [Objectives](#4-objectives)
5. [High-Level Architecture](#5-high-level-architecture)
6. [Agent Core](#6-agent-core)
7. [Agent Cycle: Perceive → Reason → Act → Check](#7-agent-cycle-perceive--reason--act--check)
8. [LLM Decision-Making & Adequacy of Resource Allocation](#8-llm-decision-making--adequacy-of-resource-allocation)
9. [Prompt Catalog](#9-prompt-catalog)
10. [Storage](#10-storage)
11. [CI/CD Integration](#11-cicd-integration)
12. [Demo Scenario](#12-demo-scenario)
13. [Assumptions and Deferred Tasks](#assumptions-and-deferred-tasks)

---

## 1. Overview

This document describes the design of **AIRIS — AI Engine for Resource Intelligence and Sizing**. AIRIS is an AI agent that analyzes Kubernetes workload resource allocations (CPU/Memory requests and limits, and storage claims), compares them against real observed usage, and produces actionable right-sizing recommendations through a CI/CD-integrated workflow. 

All reasoning, pattern recognition, and decision-making is performed by a Large Language Model (LLM). The agent contains no deterministic scoring logic or rule engines; behavior is fully encoded in prompts.

---

## 2. Problem Statement

Kubernetes workloads routinely over-allocate or under-allocate resources because:
- Engineers set initial requests/limits based on estimates rather than measurement.
- Resource profiles drift silently as application behavior changes over time.
- There is no automated feedback loop between real usage data and manifest declarations.
- Storage Persistent Volume Claims (PVCs) can balloon without review gates.

This results in wasted cluster capacity, unpredictable evictions, and unnecessary cloud spend.

---

## 3. Proposed Solution

AIRIS acts as an intelligent, centralized resource review agent. It goes beyond basic monitoring by seeking to understand the **true intention** of the application. By analyzing source code, design documents, and anticipated workloads, the AI evaluates the application's intent against its declared resources and suggests adjustments to close the gap between allocation and actual need.

---

## 4. Objectives

* **Observe** real resource consumption (CPU, memory, storage) from a live cluster.
* **Compare** actual usage against declared requests and limits.
* **Reason** about adequacy using an LLM — no hard-coded thresholds.
* **Recommend** specific manifest changes with justification in plain language.
* **Enforce a storage gate**: Any PVC claim exceeding **50 GB** must carry a written justification.
* **Integrate** into CI/CD for automated Pull Request reviews.
* **Cache** collected metrics locally (CSV for pilot) to optimize performance and avoid redundant API calls.

---

## 5. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CI/CD Trigger                            │
│           (Pull Request opened / manifest changed)              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Orchestrator                             │
│                                                                 │
│  ┌──────────┐   ┌──────────────┐   ┌───────────────────────┐    │
│  │ Perceive │──▶│    Reason    │──▶│   Act (Tool Calls)    │    │
│  └──────────┘   │   (LLM)      │   └───────────────────────┘    │
│       ▲         └──────┬───────┘              │                 │
│       │                │ Check                │                 │
│       └────────────────┴──────────────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
          │                │                  │
          ▼                ▼                ▼
   ┌─────────────┐  ┌────────────┐   ┌──────────────┐
   │  Kubernetes │  │   GitHub   │   │  Web Search  │
   │  Cluster    │  │    API     │   │              │
   └─────────────┘  └────────────┘   └──────────────┘
```

---

## 6. Agent Core

The agent consists of the **Model**, **Tools**, and **Orchestrator**.

### 6.1 Model Tiering
AIRIS uses a dual-tier strategy to balance cost and accuracy:

*   **Fast Tier (Scraping):** Optimized for high-speed pattern matching and summarization (e.g., `gpt-4o-mini`, `gemini-3.1-flash-lite`).
*   **Thinking Tier (Analysis):** Optimized for deep logical reasoning and resource calibration (e.g., `gpt-5.4-pro`, `gemini-3.1-pro`, `o1`).

### 6.2 Tools (Standard MCP)

The agent interacts with the cluster using official **Model Context Protocol (MCP)** servers. To prevent context exhaustion, the Orchestrator implements a **Projection Layer** that filters raw API responses before they reach the LLM.

| AIRIS Requirement | Standard MCP Tool | Source / URL | Orchestrator Filtering Logic |
| :--- | :--- | :--- | :--- |
| **Observe Usage** | `get_resource` (PodMetrics) | [kubernetes-mcp-server](https://github.com/modelcontextprotocol/servers/tree/main/src/kubernetes) | Extracts only `usage.cpu` and `usage.memory`; discards timestamps/window metadata. |
| **Get Allocations** | `list_resources` / `get_resource` | [kubernetes-mcp-server](https://github.com/modelcontextprotocol/servers/tree/main/src/kubernetes) | Strips `managedFields`, `ownerReferences`, and `status.conditions` from the manifest. |
| **Storage Gate Check** | `get_resource` (PVC) | [kubernetes-mcp-server](https://github.com/modelcontextprotocol/servers/tree/main/src/kubernetes) | Extracts `spec.resources.requests.storage` and `status.capacity`; flags values > 50GB. |
| **Live Disk Usage** | `exec_pod` | [kubernetes-mcp-server](https://github.com/modelcontextprotocol/servers/tree/main/src/kubernetes) | Executes `df -h`; returns only the relevant filesystem usage percentages. |
| **Review Changes** | `get_pull_request_diff` | [mcp-server-github](https://github.com/modelcontextprotocol/servers/tree/main/src/github) | Filters diffs to only include `resources:` and `storage:` blocks. |
| **Post Feedback** | `create_pull_request_review` | [mcp-server-github](https://github.com/modelcontextprotocol/servers/tree/main/src/github) | Converts structured LLM reasoning into the final Markdown PR comment. |
| **Understand Intent** | `get_file_contents` | [mcp-server-github](https://github.com/modelcontextprotocol/servers/tree/main/src/github) | Reads `README.md` or design docs; limits input to first 200 lines. |
| **Request Input** | `create_issue_comment` | [mcp-server-github](https://github.com/modelcontextprotocol/servers/tree/main/src/github) | Posts a clarifying question to the PR thread and pauses the loop. |
| **Validate Practices** | **Web Search** | **Native LLM Tool** | Verifies typical resource profiles for specific container images. |

### 6.3 Orchestrator

The Orchestrator is the state-machine runtime that drives the agent. It performs **Context Assembly** and manages **Tool Dispatching**.

To avoid exhausting the context window, the Orchestrator functions as a **Projection Layer**. It intercepts raw tool outputs and performs "JSON-thinning" before the data reaches the LLM. For example, a raw Kubernetes Pod object is thinned down to essential resource fields, reducing payload size by ~90%.

---

## 7. Agent Cycle: Perceive → Reason → Act → Check

| Phase | What happens |
|-------|-------------|
| **Step 0: Discover** | Fast-tier scan of documentation and source to establish application intent. |
| **Perceive** | Orchestrator fetches the PR diff, history, and cluster metrics. |
| **Reason** | Thinking-tier LLM evaluates metrics against the discovered intent. |
| **Act** | LLM issues tool calls (metrics, PVC checks, etc.) via Orchestrator. |
| **Check** | LLM reviews outputs; loops back or provides final recommendation. |

---

## 8. LLM Decision-Making & Adequacy

The LLM evaluates adequacy across four dimensions:

1.  **Utilisation Band**: (Under-provisioned >85%, Well-utilised 40–85%, Over-provisioned <40%).
2.  **Statistical Confidence**: Lowers confidence if snapshots are limited (<3).
3.  **Workload Archetype**: Adjusts margins based on whether the app is an API, Batch, or Database.
4.  **Change Risk Assessment**: Evaluates reversibility and blast radius.

---

## 9. Prompt Catalog

Prompts are stored as versioned files in `agent/prompts/`:
* **`system.txt`**: Role definition and the Perceive-Reason-Act-Check contract.
* **`analyse_resources.txt`**: Logic for adequacy assessment.
* **`storage_gate.txt`**: Logic for PVCs > 50 GB.
* **`confidence_calibration.txt`**: Self-review to lower confidence.
* **`format_pr_comment.txt`**: Converts reasoning into Markdown.

---

## 10. Storage

### 10.1 Metrics Cache (Pilot)
Metrics are persisted as CSV files in `./data/`:
* `metrics_cache.csv`: Pod resource snapshots.
* `pvc_cache.csv`: Storage claim vs. actual usage.
* `run_findings.csv`: Summary of findings per agent run.

### 10.2 Intent Cache
Technical intent discovered during Step 0 is cached locally as JSON in `.data/{workload}_intent_cache.json`. This ensures that subsequent runs reuse the derived "Technical Intent Summary," reducing both latency and API costs.

---

## 11. CI/CD Integration

The workflow triggers on `pull_request` events targeting `.yaml` files.
* **APPROVE**: All allocations adequate.
* **COMMENT**: Over-provisioning detected (low risk).
* **REQUEST_CHANGES**: Under-provisioning or Storage Gate violation.

---

## 12. Demo Scenario

1.  **Workload**: `payments-db` claims 200Gi but uses only 12Gi.
2.  **Detection**: Agent identifies the 50GB threshold is exceeded without justification.
3.  **Action**: Agent triggers `request_human_input` via GitHub comment.

---

### Assumptions and Deferred Tasks
1.  **Security / RBAC Permissions**: Read-only access is assumed feasible.
2.  **Smart Cache**: Persisting application "intent" is a future ToDo.
