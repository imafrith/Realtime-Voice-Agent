import asyncio
import base64
import json
import os

import audioop
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import Response
from pydantic import BaseModel
import websockets
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash-native-audio-preview-09-2025"
GEMINI_WS_URL = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
    f"?key={GEMINI_API_KEY}"
)
SYSTEM_INSTRUCTION = """
You are Priya, a friendly and persuasive sales counselor at TechEdge Academy, a leading tech training institute.

STRICT RULES:
- NEVER say you are an AI, a language model, Gemini, or a virtual assistant. You are Priya, a real person.
- If asked "Are you a robot/AI?", say "No no, I'm Priya from TechEdge Academy's admissions team!"
- Keep responses short, warm, and conversational — like a real phone call.
- Speak in a natural, enthusiastic tone. Use phrases like "That's a great choice!", "Let me tell you about this amazing program."
- Always try to close the sale — ask for enrollment, offer limited-time discounts, create urgency.
- Ask the caller's name early and use it throughout the conversation.

COURSES CATALOG:

1. Data Science & Machine Learning
   - Duration: 6 months
   - Price: ₹45,000 (or 3 EMIs of ₹16,000)
   - Covers: Python, Statistics, ML algorithms, Deep Learning, NLP, Computer Vision, Capstone project
   - Job roles: Data Scientist, ML Engineer, AI Developer
   - Placement support: Yes, 95% placement rate

2. Data Analytics
   - Duration: 4 months
   - Price: ₹30,000 (or 3 EMIs of ₹11,000)
   - Covers: Excel, SQL, Power BI, Tableau, Python for analytics, Statistics, Real-world projects
   - Job roles: Data Analyst, Business Analyst, BI Analyst
   - Placement support: Yes

3. Python Full Stack Development
   - Duration: 5 months
   - Price: ₹40,000 (or 3 EMIs of ₹14,500)
   - Covers: Python, Django, REST APIs, React.js, HTML/CSS, PostgreSQL, Git, Deployment, 3 live projects
   - Job roles: Full Stack Developer, Backend Developer, Python Developer
   - Placement support: Yes

4. Data Engineering
   - Duration: 5 months
   - Price: ₹50,000 (or 3 EMIs of ₹18,000)
   - Covers: Python, SQL, Apache Spark, Kafka, Airflow, AWS/GCP, ETL pipelines, Data warehousing
   - Job roles: Data Engineer, ETL Developer, Big Data Engineer
   - Placement support: Yes

5. DevOps Engineering
   - Duration: 4 months
   - Price: ₹35,000 (or 3 EMIs of ₹12,500)
   - Covers: Linux, Docker, Kubernetes, Jenkins, Terraform, AWS, CI/CD pipelines, Monitoring
   - Job roles: DevOps Engineer, Cloud Engineer, SRE
   - Placement support: Yes

6. Networking & Cybersecurity
   - Duration: 4 months
   - Price: ₹32,000 (or 3 EMIs of ₹11,500)
   - Covers: CCNA, Network security, Firewalls, Ethical hacking, SIEM tools, Cloud security
   - Certifications: Prepares for CCNA, CompTIA Security+
   - Job roles: Network Engineer, Security Analyst, SOC Analyst
   - Placement support: Yes

SALES TACTICS:
- If the caller is interested, mention "We have a limited-time 10% early bird discount if you enroll this week."
- Highlight placement support and mention "Our students are working at top MNCs like TCS, Infosys, Wipro, Amazon, and startups."
- If they hesitate on price, offer the EMI option: "We have easy EMI options, so you can start learning without any financial burden."
- If unsure which course, ask about their background and career goals, then recommend the best fit.
- Always end with a clear next step: "Shall I book a seat for you?" or "Can I schedule a free demo class for you?"
- Collect their name, email, and preferred batch timing if they show interest.
"""
VOICE = "Aoede"  # Options: Aoede, Charon, Fenrir, Kore, Puck

# --- Twilio credentials ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
SERVER_URL = os.getenv("SERVER_URL", "").rstrip("/")
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# --- Audio format constants ---
TWILIO_SAMPLE_RATE = 8000   # Twilio sends/receives mulaw at 8kHz
GEMINI_INPUT_RATE = 16000   # Gemini expects PCM input at 16kHz
GEMINI_OUTPUT_RATE = 24000  # Gemini returns PCM output at 24kHz


@app.api_route("/incoming-call", methods=["GET", "POST"])
async def incoming_call(request: Request):
    """Twilio webhook — returns TwiML that opens a Media Stream WebSocket."""
    host = request.headers.get("host", "localhost")
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}/media-stream" />
    </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


class OutboundCallRequest(BaseModel):
    to: str  # Phone number to call, e.g. "+1234567890"


@app.post("/outbound-call")
async def outbound_call(body: OutboundCallRequest):
    """Initiate an outbound call that connects to the Gemini voice agent."""
    if not SERVER_URL:
        return {"error": "SERVER_URL not set in .env — add your ngrok public URL"}

    twiml_url = f"{SERVER_URL}/outbound-twiml"

    call = twilio_client.calls.create(
        to=body.to,
        from_=TWILIO_PHONE_NUMBER,
        url=twiml_url,
    )
    print(f"[Outbound] Call initiated — SID: {call.sid}, To: {body.to}")
    return {"status": "calling", "call_sid": call.sid, "to": body.to}


@app.api_route("/outbound-twiml", methods=["GET", "POST"])
async def outbound_twiml(request: Request):
    """TwiML for outbound calls — connects to Media Stream with outbound flag."""
    host = request.headers.get("host", "localhost")
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Please hold while we connect you.</Say>
    <Connect>
        <Stream url="wss://{host}/media-stream?direction=outbound" />
    </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    """Bridges Twilio Media Stream ↔ Gemini Live API."""
    await websocket.accept()

    # Detect if this is an outbound call
    direction = websocket.query_params.get("direction", "inbound")
    print(f"[Twilio] WebSocket connected — direction: {direction}")

    stream_sid = None

    # Connect to Gemini Live API
    try:
        gemini_ws = await websockets.connect(
            GEMINI_WS_URL,
            additional_headers={"Content-Type": "application/json"},
        )
    except Exception as e:
        print(f"[Gemini] Failed to connect: {e}")
        await websocket.close()
        return

    # Send setup message to Gemini
    setup_msg = {
        "setup": {
            "model": f"models/{GEMINI_MODEL}",
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": VOICE,
                        }
                    }
                },
            },
            "systemInstruction": {
                "parts": [{"text": SYSTEM_INSTRUCTION}]
            },
        }
    }
    await gemini_ws.send(json.dumps(setup_msg))

    # Wait for setup confirmation
    setup_response = json.loads(await gemini_ws.recv())
    print(f"[Gemini] Setup complete: {setup_response}")

    # For outbound calls, prompt Gemini to greet the caller first
    if direction == "outbound":
        await gemini_ws.send(json.dumps({
            "clientContent": {
                "turns": [{
                    "role": "user",
                    "parts": [{"text": "Greet the caller. You placed this call, so introduce yourself and ask how you can help."}]
                }],
                "turnComplete": True,
            }
        }))
        print("[Gemini] Sent initial greeting prompt for outbound call")

    # ---- Gemini → Twilio (AI audio out to caller) ----
    async def gemini_to_twilio():
        nonlocal stream_sid
        try:
            async for message in gemini_ws:
                response = json.loads(message)

                # Extract audio from serverContent
                server_content = response.get("serverContent")
                if not server_content:
                    continue

                model_turn = server_content.get("modelTurn", {})
                parts = model_turn.get("parts", [])

                for part in parts:
                    inline_data = part.get("inlineData")
                    if not inline_data:
                        continue

                    mime = inline_data.get("mimeType", "")
                    if "audio/pcm" not in mime:
                        continue

                    # Decode Gemini's PCM 16-bit 24kHz audio
                    pcm_24k = base64.b64decode(inline_data["data"])

                    # Resample 24kHz → 8kHz for Twilio
                    pcm_8k, _ = audioop.ratecv(
                        pcm_24k, 2, 1, GEMINI_OUTPUT_RATE, TWILIO_SAMPLE_RATE, None
                    )

                    # Convert PCM → mulaw (what Twilio expects)
                    mulaw_audio = audioop.lin2ulaw(pcm_8k, 2)

                    # Send to Twilio as base64
                    if stream_sid:
                        await websocket.send_json({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": base64.b64encode(mulaw_audio).decode()
                            },
                        })

                # Handle interruption — clear Twilio's audio queue
                if server_content.get("interrupted"):
                    if stream_sid:
                        await websocket.send_json({
                            "event": "clear",
                            "streamSid": stream_sid,
                        })
                        print("[Twilio] Cleared audio queue (interruption)")

        except websockets.exceptions.ConnectionClosed:
            print("[Gemini] Connection closed")
        except Exception as e:
            print(f"[Gemini→Twilio] Error: {e}")

    # Start forwarding task
    gemini_task = asyncio.create_task(gemini_to_twilio())

    # ---- Twilio → Gemini (caller audio in to AI) ----
    try:
        async for message in websocket.iter_text():
            data = json.loads(message)
            event = data.get("event")

            if event == "start":
                stream_sid = data["start"]["streamSid"]
                print(f"[Twilio] Stream started — SID: {stream_sid}")

            elif event == "media":
                # Decode Twilio's base64 mulaw audio
                mulaw_audio = base64.b64decode(data["media"]["payload"])

                # Convert mulaw → PCM 16-bit
                pcm_audio = audioop.ulaw2lin(mulaw_audio, 2)

                # Resample 8kHz → 16kHz for Gemini
                pcm_16k, _ = audioop.ratecv(
                    pcm_audio, 2, 1, TWILIO_SAMPLE_RATE, GEMINI_INPUT_RATE, None
                )

                # Send to Gemini Live API
                await gemini_ws.send(json.dumps({
                    "realtimeInput": {
                        "mediaChunks": [{
                            "mimeType": "audio/pcm;rate=16000",
                            "data": base64.b64encode(pcm_16k).decode(),
                        }]
                    }
                }))

            elif event == "stop":
                print("[Twilio] Stream stopped")
                break

    except Exception as e:
        print(f"[Twilio→Gemini] Error: {e}")
    finally:
        gemini_task.cancel()
        await gemini_ws.close()
        print("[Server] Session ended")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
