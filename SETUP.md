# Voice Agent — Twilio + Gemini Live API

Real-time voice calling agent that connects phone calls directly to Gemini's native audio model. No STT or TTS needed.

## Architecture

```
Your Phone  →  dials Twilio number
                    ↓
Twilio      →  hits /incoming-call webhook
                    ↓
Server      →  returns TwiML → opens WebSocket to /media-stream
                    ↓
Server      →  connects to Gemini Live API (native audio)
                    ↓
Your voice  →  mulaw→PCM→16kHz  →  Gemini  →  PCM 24kHz→mulaw  →  you hear AI
```

## Prerequisites

- Python 3.10+
- Twilio account with a phone number
- Gemini API key (with native audio model access)
- ngrok account (free tier works)

## Setup

### 1. Install Dependencies

```bash
cd "C:\Users\Tech_Pc_New_01\Desktop\voice agent"
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file (use `.env.example` as reference):

```
GEMINI_API_KEY=your-gemini-api-key
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_PHONE_NUMBER=+1234567890
```

### 3. Install ngrok

Download from [ngrok.com/download](https://ngrok.com/download) or:

```bash
choco install ngrok
```

Authenticate once:

```bash
ngrok config add-authtoken YOUR_NGROK_TOKEN
```

## Running the Agent

### Step 1 — Start the server

```bash
python main.py
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 2 — Start ngrok (in a second terminal)

```bash
ngrok http 8000
```

Copy the public URL (e.g. `https://abc123.ngrok-free.app`).

### Step 3 — Configure Twilio webhook

1. Go to [Twilio Console](https://console.twilio.com)
2. Navigate to **Phone Numbers → Manage → Active Numbers**
3. Click on your phone number
4. Under **Voice Configuration**:
   - **"A call comes in"** → Webhook
   - **URL:** `https://abc123.ngrok-free.app/incoming-call`
   - **Method:** HTTP POST
5. Click **Save Configuration**

### Step 4 — Make a call

Call your Twilio phone number from any phone. You'll be connected to the AI agent. Just start talking.

## Project Structure

```
voice-agent/
├── main.py             # FastAPI server (Twilio ↔ Gemini bridge)
├── .env                # API keys and credentials
├── .env.example        # Environment template
├── requirements.txt    # Python dependencies
└── SETUP.md            # This file
```

## How It Works

| Component | Role |
|-----------|------|
| `/incoming-call` | Twilio webhook — returns TwiML that opens a Media Stream |
| `/media-stream` | WebSocket endpoint — bridges Twilio ↔ Gemini audio |
| **Twilio → Gemini** | Decodes mulaw 8kHz → PCM 16kHz, sends to Gemini |
| **Gemini → Twilio** | Converts PCM 24kHz → mulaw 8kHz, sends to caller |
| **Interruption** | Clears Twilio audio queue when caller speaks over AI |

## Audio Format Reference

| Direction | Twilio Format | Gemini Format |
|-----------|--------------|---------------|
| Inbound (caller → AI) | mulaw, 8kHz, base64 | PCM 16-bit, 16kHz |
| Outbound (AI → caller) | mulaw, 8kHz, base64 | PCM 16-bit, 24kHz |

## Configuration

Edit these values in `main.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_MODEL` | `gemini-2.5-flash-native-audio-preview-09-2025` | Gemini model ID |
| `VOICE` | `Aoede` | Voice name (`Aoede`, `Charon`, `Fenrir`, `Kore`, `Puck`) |
| `SYSTEM_INSTRUCTION` | *"You are a helpful AI phone assistant..."* | Agent personality/instructions |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `[Gemini] Failed to connect` | Check `GEMINI_API_KEY` in `.env` |
| Call rings but no audio | Verify ngrok is running and Twilio webhook URL matches |
| `audioop` import error | Run `pip install audioop-lts` (Python 3.13+) |
| Choppy / no AI audio | Verify the model supports native audio in your Gemini plan |
| Webhook not reachable | Every ngrok restart gives a new URL — update Twilio accordingly |
