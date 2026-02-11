# Realtime Voice Agent — Twilio + Gemini Live API

A real-time AI voice calling agent built with **Twilio** and **Google Gemini Live API**. No STT or TTS services needed — Gemini's native audio model handles voice-in and voice-out directly over a phone call.

## Features

- **Inbound calls** — Callers dial your Twilio number and talk to the AI agent instantly
- **Outbound calls** — Trigger a call via API, the AI agent dials the person and starts the conversation
- **Real-time streaming** — Bidirectional audio over WebSocket, no waiting for full responses
- **Native voice-to-voice** — Gemini processes raw audio directly, no separate STT/TTS pipeline
- **Interruption handling** — Caller can interrupt the AI mid-sentence, audio queue clears instantly
- **Customizable persona** — Configure the agent's personality, voice, and knowledge via system prompt

## Architecture

```
Phone Call ──→ Twilio ──→ WebSocket (Media Streams) ──→ FastAPI Server ──→ Gemini Live API
                                                              ↕
Phone Call ←── Twilio ←── WebSocket (Media Streams) ←── FastAPI Server ←── Gemini Live API
```

### Audio Pipeline

| Direction | Twilio Format | Conversion | Gemini Format |
|-----------|--------------|------------|---------------|
| Caller → AI | mulaw 8kHz base64 | → PCM 16-bit → resample 16kHz | PCM 16kHz |
| AI → Caller | mulaw 8kHz base64 | ← PCM 16-bit ← resample 8kHz | PCM 24kHz |

## Tech Stack

- **FastAPI** — Async web server with WebSocket support
- **Twilio Media Streams** — Real-time audio streaming over phone calls
- **Gemini Live API** — Google's native audio multimodal model (`gemini-2.5-flash-native-audio-preview`)
- **audioop** — Audio format conversion (mulaw ↔ PCM, resampling)

## Setup

### Prerequisites

- Python 3.10+
- Twilio account with a phone number
- Google Gemini API key (with native audio model access)
- ngrok or public URL for Twilio webhooks

### Installation

```bash
git clone https://github.com/your-username/voice-agent.git
cd voice-agent
pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```env
GEMINI_API_KEY=your-gemini-api-key
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_PHONE_NUMBER=+1234567890
SERVER_URL=https://your-public-url.ngrok-free.app
```

### Running

```bash
# Start the server
python main.py

# Expose with ngrok (in a second terminal)
ngrok http 8000
```

Set your Twilio phone number's Voice webhook to:
```
https://your-ngrok-url.ngrok-free.app/incoming-call
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/incoming-call` | GET/POST | Twilio webhook — returns TwiML to open Media Stream |
| `/outbound-call` | POST | Initiate an outbound call to a phone number |
| `/outbound-twiml` | GET/POST | TwiML for outbound calls (used internally by Twilio) |
| `/media-stream` | WebSocket | Bidirectional audio bridge between Twilio and Gemini |

### Make an Outbound Call

```bash
curl -X POST http://localhost:8000/outbound-call \
  -H "Content-Type: application/json" \
  -d '{"to": "+1234567890"}'
```

## Customization

Edit `main.py` to change:

| Variable | Description |
|----------|-------------|
| `SYSTEM_INSTRUCTION` | Agent persona, knowledge base, and behavior rules |
| `VOICE` | Gemini voice — `Aoede`, `Charon`, `Fenrir`, `Kore`, or `Puck` |
| `GEMINI_MODEL` | Gemini model ID |

## Project Structure

```
voice-agent/
├── main.py             # FastAPI server — Twilio ↔ Gemini audio bridge
├── .env                # API keys and credentials (not committed)
├── .env.example        # Environment template
├── requirements.txt    # Python dependencies
├── SETUP.md            # Detailed setup guide
└── README.md           # This file
```

## License

MIT
