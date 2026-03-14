# Specification: tj-6mv-voice (Voice message recognition)

## 1. Goal
Implement voice message recognition using the `mistralai/voxtral-small-24b-2507` model via OpenRouter, replacing the originally planned Whisper API setup. The model supports both text and audio inputs and handles English and Arabic natively.

## 2. Requirements
- Handle Wazzup webhook incoming messages of type `audio` / `voice`.
- Download the audio payload from Wazzup API.
- Send the audio as a base64 string to the OpenRouter API with `mistralai/voxtral-small-24b-2507` specifically requesting a raw accurate transcription.
- Update the `.env` default model to point to `mistralai/voxtral-small-24b-2507` universally.
- Save both the original audio URL and the transcribed text in the `Message` database model.
- Forward the transcribed text into the existing `process_message` flow so the LLM responds exactly as if it were a typed message.
- Full unit tests for the transcriber and the webhook handler.

## 3. Architecture & Data Flow
1. **Webhook Reception:** `src/api/v1/webhook.py` receives a message with `type="audio"` or `type="voice"`.
2. **Audio Download:** A new method `download_media(url: str) -> bytes` in `src/integrations/messaging/wazzup.py` fetches the audio content.
3. **Voxtral Transcription:** A new service module `src/integrations/voice/voxtral.py` calls OpenRouter's `/chat/completions` API using the standard OpenAI payload format for audio (`"type": "input_audio"`, `"input_audio": {"data": base64_str, "format": "mp3"}`). It uses an HTTP client (`httpx`).
4. **Database Storage:** `src/models/message.py` receives two new columns: `audio_url` (String) and `transcription` (Text). Alembic migration created.
5. **LLM Flow:** The transcribed text is treated as `message.content` and sent to the LLM agent via `process_message` in `src/services/chat.py`. 
6. **Main Model Update:** `src/core/config.py` default `openrouter_model_main` is set to `mistralai/voxtral-small-24b-2507`.

## 4. Models & API Contracts
### 4.1. Message Model
New fields:
- `audio_url: Mapped[str | None]`
- `transcription: Mapped[str | None]`

### 4.2. OpenRouter Audio API Payload
```json
{
  "model": "mistralai/voxtral-small-24b-2507",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Please transcribe this audio exactly as spoken in its original language (Arabic or English). Only return the transcription, without any markdown formatting or extra conversational text."
        },
        {
          "type": "input_audio",
          "input_audio": {
            "data": "<BASE64_ENCODED_AUDIO_BYTES>",
            "format": "mp3"
          }
        }
      ]
    }
  ]
}
```

## 5. Security & Error Handling
- Timeout set to 30s for the transcriber to handle larger audio files.
- If transcription fails or returns an API error (e.g., format unsupported), gracefully log the error, and send a standard response: "Sorry, I couldn't understand the voice message. Could you please type it instead?"
- PII Masking: The text returned by the transcriber will immediately go through the standard `mask_pii` step before hitting the main reasoning loops.
