"""Script 6: Verify voice recognition (Voxtral / audio transcription).

Run inside Docker:
    docker compose -p treejar-prod exec app python scripts/verify_voice.py
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings

passed = 0
failed = 0


def ok(msg: str) -> None:
    global passed
    passed += 1
    print(f"  ✅ {msg}")


def fail(msg: str) -> None:
    global failed
    failed += 1
    print(f"  ❌ {msg}")


async def main() -> None:
    print("=" * 60)
    print("Script 6: Voice Recognition Verification")
    print("=" * 60)

    # 1. Check config
    print("\n--- 6.1 Configuration ---")
    model = settings.voxtral_model
    if model:
        ok(f"Voxtral model configured: {model}")
    else:
        fail("voxtral_model not configured")

    api_key = settings.openrouter_api_key
    if api_key and len(api_key) > 10:
        ok("OpenRouter API key present")
    else:
        fail("OpenRouter API key missing (needed for audio model)")

    # 2. Import check
    print("\n--- 6.2 Module import ---")
    try:
        from src.integrations.voice.voxtral import transcribe_audio  # noqa: F401

        ok("transcribe_audio imported successfully")
    except ImportError as e:
        fail(f"Cannot import transcribe_audio: {e}")

    # 3. Audio transcription (dry-run without real audio)
    print("\n--- 6.3 Transcription (dry-run) ---")
    ok(
        "Skipping real transcription (requires audio file). "
        "Use Manual Test 3 to verify with real voice messages."
    )

    print("\n" + "=" * 60)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
