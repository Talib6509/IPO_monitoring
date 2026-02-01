This project implements a scheduled, production-style automation system that monitors same-day U.S. IPOs, filters for large offerings (>$200M), and sends a daily email alert with a human-readable summary.
The system is designed to be:
-Deterministic and reliable
-Configurable via environment variables
-Safe in its use of LLMs (LLMs are used only for text generation, not decision-making)

Key Features:
-Daily scheduled execution using APScheduler (cron-style)
-State-based workflow orchestration using LangGraph
-Real-world market data ingestion via IPO API
-Rule-based filtering for large IPOs
-LLM-generated email content with strict prompt constraints
-SMTP email delivery using Gmail App Passwords
-Fully configurable without code changes

Workflow Description
1. IPO Monitoring
-Fetches IPOs scheduled for the current day only
-Uses timezone-aware date logic (Asia/Dubai)
-Returns structured IPO data

2. Business Rule Filtering
-Filters for:
-USD-denominated IPOs
-Total offer size greater than $200 million
-Extracts only relevant metadata:
---Ticker
---Issuer name
---IPO status
---Announced date
---Final issue price
---Total offer size

3. Email Notification
-Uses an LLM to generate a plain-text summary
-Prompt is strictly constrained:
-No hallucinations
-No speculative language
-No formatting ambiguity
-Email is sent only if qualifying IPOs exist
