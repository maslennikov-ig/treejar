# Voice Message Recognition (Voxtral) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement voice message processing by downloading audio from Wazzup and transcribing it via OpenRouter's `mistralai/voxtral-small-24b-2507` model.

**Architecture:** 
- The `Message` model will store `audio_url` and `transcription`.
- Wazzup provider gets a `download_media()` method.
- A new `src/integrations/voice/voxtral.py` module handles the OpenRouter audio prompt.
- The Wazzup webhook routes audio messages -> downloads audio -> transcribes -> saves to DB -> sends to `process_message`.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, httpx (for OpenRouter API), pytest.

---

### Task 1: Update Configuration & Database Model

**Files:**
- Modify: `src/core/config.py`
- Modify: `src/models/message.py`
- Create: Alembic migration

**Step 1: Write the failing test**
Create `tests/test_task01_voice_model.py`:
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.config import settings
from src.models.message import Message

async def test_message_has_audio_fields(db_session: AsyncSession):
    msg = Message(
        conversation_id="123e4567-e89b-12d3-a456-426614174000",
        role="user",
        content="test",
        audio_url="https://url.com/a.ogg",
        transcription="transcribed text"
    )
    db_session.add(msg)
    await db_session.commit()
    assert msg.audio_url == "https://url.com/a.ogg"
    assert msg.transcription == "transcribed text"

def test_config_model():
    assert settings.openrouter_model_main == "mistralai/voxtral-small-24b-2507"
```

**Step 2: Run test to verify it fails**
Run: `pytest tests/test_task01_voice_model.py -v`
Expected: FAIL due to missing fields / wrong model string.

**Step 3: Write minimal implementation**
1. In `src/core/config.py`: change `openrouter_model_main: str = "z-ai/glm-5"` (or current) to `"mistralai/voxtral-small-24b-2507"`.
2. In `src/models/message.py`: add `audio_url: Mapped[str | None]` and `transcription: Mapped[str | None]`.
3. Run `alembic revision --autogenerate -m "add audio fields to message"`
4. Run `alembic upgrade head`.

**Step 4: Run test to verify it passes**
Run: `pytest tests/test_task01_voice_model.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/core/config.py src/models/message.py migrations/ tests/
git commit -m "feat: add audio fields to message model and update main llm"
```

---

### Task 2: Wazzup Audio Downloader

**Files:**
- Modify: `src/integrations/messaging/wazzup.py`
- Modify: `tests/test_wazzup.py`

**Step 1: Write the failing test**
In `tests/test_wazzup.py`, add `test_download_media_success`:
Mock `httpx.AsyncClient.request` to return HTTP 200 with bytes `b"audio"`. Call `wazzup.download_media("http://test.url/media")` and assert it returns `b"audio"`.

**Step 2: Run test to verify it fails**
Run: `pytest tests/test_wazzup.py -k test_download_media -v`
Expected: FAIL `AttributeError: download_media`.

**Step 3: Write minimal implementation**
In `src/integrations/messaging/wazzup.py`, add:
```python
    async def download_media(self, url: str) -> bytes:
        """Download media from Wazzup CDNs."""
        response = await self._request("GET", url)
        return response.content
```

**Step 4: Run test to verify it passes**
Run: `pytest tests/test_wazzup.py -k test_download_media -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/integrations/messaging/wazzup.py tests/test_wazzup.py
git commit -m "feat: wazzup media downloader"
```

---

### Task 3: Voxtral Transcriber Service

**Files:**
- Create: `src/integrations/voice/voxtral.py`
- Create: `tests/test_voxtral.py`

**Step 1: Write the failing test**
In `tests/test_voxtral.py`:
Write `test_transcribe_audio`: mock `httpx.AsyncClient.post` to return a fake JSON OpenAI response with `{ "choices": [{"message": {"content": "hello world"}}] }`. Asserts `transcribe_audio(b"fake_audio") == "hello world"`.

**Step 2: Run test to verify it fails**
Run: `pytest tests/test_voxtral.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'src.integrations.voice'`.

**Step 3: Write minimal implementation**
Create `src/integrations/voice/voxtral.py`. Use `httpx` to POST to `https://openrouter.ai/api/v1/chat/completions`.
- Encode bytes to base64.
- Payload format: `messages=[{"role": "user", "content": [{"type":"text", "text":"...transcribe exactly..."}, {"type":"input_audio", "input_audio":{"data": b64, "format":"mp3"}}]}]`
- Model: `settings.openrouter_model_main`
- Extract and return `response.json()["choices"][0]["message"]["content"]`.

**Step 4: Run test to verify it passes**
Run: `pytest tests/test_voxtral.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/integrations/voice/voxtral.py tests/test_voxtral.py
git commit -m "feat: voxtral openrouter transcriber"
```

---

### Task 4: Webhook Integration

**Files:**
- Modify: `src/api/v1/webhook.py`
- Modify: `tests/test_webhook_manager.py` (or create `test_webhook_audio.py`)

**Step 1: Write the failing test**
Create `tests/test_webhook_audio.py`. Send a webhook payload mimicking Wazzup audio message (`type="audio"`, `media={"url": "http..."}`). Mock `download_media` and `transcribe_audio`. Assert that `process_message` is called with the transcribed text.

**Step 2: Run test to verify it fails**
Run: `pytest tests/test_webhook_audio.py -v`
Expected: FAIL because webhook ignores `audio` or fails to transcribe.

**Step 3: Write minimal implementation**
In `src/api/v1/webhook.py`:
1. If `msg.type in ("audio", "voice")`:
2. Call `await wazzup.download_media(msg.media.url)`
3. Call `transcribed_text = await transcribe_audio(audio_bytes)`
4. Set `db_msg.audio_url = msg.media.url` and `db_msg.transcription = transcribed_text`
5. Treat `transcribed_text` as the message content, feed it to `process_message`.

**Step 4: Run test to verify it passes**
Run: `pytest tests/test_webhook_audio.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/api/v1/webhook.py tests/test_webhook_audio.py
git commit -m "feat: handle audio messages in wazzup webhook"
```
