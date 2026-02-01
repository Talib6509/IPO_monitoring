from langgraph.graph import StateGraph, END
from pydantic import BaseModel
from typing import List, Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import time

from langchain_ibm import WatsonxLLM
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

from dotenv import load_dotenv
import os
import logging
import json

import datetime
import pytz
from massive import RESTClient


import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# logging.basicConfig(level=logging.INFO)


load_dotenv()
wx_api = os.getenv("APIKEY")
project_id = os.getenv("PROJECT_ID")

SENDER_EMAIL = os.getenv("EMAIL_FROM")
APP_PASSWORD = os.getenv("EMAIL_PASSWORD")
RECIPIENT_EMAIL = os.getenv("EMAIL_TO")

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "9"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))
SCHEDULE_TIMEZONE = os.getenv("SCHEDULE_TIMEZONE")



client = RESTClient(POLYGON_API_KEY)

# ============================================================
# 2. CONFIGURE WATSONX LLM
# ============================================================
llm = WatsonxLLM(
    model_id="mistralai/mistral-medium-2505",
    url="https://us-south.ml.cloud.ibm.com",
    apikey=wx_api,
    project_id=project_id,
    params={
        GenParams.MAX_NEW_TOKENS: 3000,
        GenParams.TEMPERATURE: 0,
    },
)

# ============================================================
# 3. DEFINE STATE GRAPH MODELS
# ============================================================
class IPOState(BaseModel):
    ipos: List[Any] = []
    qualified_tickers: List[dict] = []





def monitor_ipos(state: IPOState):
    dubai_tz = pytz.timezone("Asia/Dubai")

    today = datetime.datetime.now(dubai_tz).date().isoformat()

    ipos = []
    for ipo in client.vx.list_ipos(
        listing_date_gte=today,
        # listing_date_lte=today,
        order="desc",
        limit=120,
        sort="listing_date",
        ):
        ipos.append(ipo)
    
    print("------------------------------------------------------------------------")

    print(f"Found {len(ipos)} IPOs listed on or after {today}")
    # print(f"IPOs: {ipos}")

    return {"ipos": ipos}

def filter_large_ipos(state: IPOState):
    qualified = []

    for ipo in state.ipos:
        if ipo.currency_code != "USD":
            continue  # optional safety

        offer_size = ipo.total_offer_size
        if offer_size is None:
            continue

        if offer_size > 200_000_000:
            qualified.append({
                "ticker": ipo.ticker,
                "issuer_name": ipo.issuer_name,
                "ipo_status": ipo.ipo_status,
                "announced_date": ipo.announced_date,
                "final_issue_price": ipo.final_issue_price,
                "total_offer_size": ipo.total_offer_size,
            })
    print("------------------------------------------------------------------------")

    print(f"Qualified IPOs with offer size > $200M: {len(qualified)}")
    print(f"Qualified IPOs: {qualified}")

    return {"qualified_tickers": qualified}

def email_node(state: IPOState):
    send_ipo_email(state.qualified_tickers)
    return {}





def send_ipo_email(tickers: List[dict]):
    if not tickers:
        return  # nothing to send

    subject = "Daily IPO Alert – Offer Size > USD 200M"


    prompt = f"""
You are generating the body of an automated financial alert email.

Task:
Provide a detailed summary for each IPO listed in the data.

Audience:
A technically literate professional (finance / engineering background).

Tone:
Clear, concise, factual, and professional.
No marketing language. No speculation. No emojis.

Instructions:
- Do NOT invent or assume any information.
- Use ONLY the data provided.
- If a field is missing or null, explicitly write "Not disclosed".
- Format the email in plain text.
- Use bullet points per IPO.
- Do NOT include a subject line.
- Do NOT include greetings or signatures.

For each IPO, include:
- Ticker
- Issuer name
- IPO status
- Announced date
- Final issue price
- Total offer size (USD, formatted with commas)

IPO data:
{json.dumps(tickers, indent=2)}

Output:"""

    body = llm.invoke(prompt).strip()



    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(SENDER_EMAIL, APP_PASSWORD)
    server.send_message(msg)
    server.quit()

    print("------------------------------------------------------------------------")
    print("IPO alert email sent.")


# ============================================================
# 4. BUILD LANGGRAPH WORKFLOW
# ============================================================

graph = StateGraph(IPOState)

graph.add_node("monitor_ipos", monitor_ipos)
graph.add_node("filter_large_ipos", filter_large_ipos)
graph.add_node("send_email", email_node)

graph.set_entry_point("monitor_ipos")

graph.add_edge("monitor_ipos", "filter_large_ipos")
graph.add_edge("filter_large_ipos", "send_email")
graph.add_edge("send_email", END)

workflow = graph.compile()



# ============================================================
# APP & SCHEDULER
# ============================================================

scheduler = BackgroundScheduler(
    timezone=pytz.timezone("Asia/Dubai")
)

def run_workflow():
    try:
        logging.info("Running daily IPO LangGraph workflow")
        workflow.invoke({})
    except Exception as e:
        logging.exception("IPO workflow failed", exc_info=e)


print(SCHEDULE_HOUR, SCHEDULE_MINUTE, SCHEDULE_TIMEZONE)
scheduler.add_job(
    run_workflow,
    CronTrigger(
        hour=SCHEDULE_HOUR,
        minute=SCHEDULE_MINUTE,
        timezone=SCHEDULE_TIMEZONE
    ),
    id="daily_ipo_job",
    replace_existing=True,
)

scheduler.start()
logging.info("Scheduler started (09:00 Asia/Dubai)")

while True:
    time.sleep(60)







