import argparse
import os
import wave
from pathlib import Path

from google import genai
from google.genai import types


def save_wav(filename: Path, pcm_data: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> None:
    with wave.open(str(filename), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(rate)
        wav_file.writeframes(pcm_data)


def wav_duration_seconds(filename: Path) -> float:
    with wave.open(str(filename), "rb") as wav_file:
        return wav_file.getnframes() / float(wav_file.getframerate())


def build_tts_prompt(script_text: str) -> str:
    return (
        "You are a professional product demo narrator. "
        "Read the transcript naturally in clear, warm English with a steady pace suitable for a 2 minute 8 second demo. "
        "Do not read section timestamps or bracketed ranges aloud. "
        "Keep delivery polished, confident, and easy to follow.\n\n"
        "TRANSCRIPT:\n"
        f"{script_text}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a voiceover WAV from the 2:08 script using Gemini TTS.")
    parser.add_argument(
        "--script",
        default="voiceover_script_2m08.txt",
        help="Path to the script text file.",
    )
    parser.add_argument(
        "--output",
        default="voiceover_2m08_gemini.wav",
        help="Output WAV path.",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash-preview-tts",
        help="Gemini TTS model.",
    )
    parser.add_argument(
        "--voice",
        default="Sulafat",
        help="Gemini prebuilt voice name.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in the environment.")

    script_path = Path(args.script).resolve()
    output_path = Path(args.output).resolve()

    script_text = script_path.read_text(encoding="utf-8")

    client = genai.Client(api_key=api_key)
    prompt = build_tts_prompt(script_text)

    response = client.models.generate_content(
        model=args.model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=args.voice)
                )
            ),
        ),
    )

    pcm_data = response.candidates[0].content.parts[0].inline_data.data
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_wav(output_path, pcm_data)

    duration = wav_duration_seconds(output_path)
    print(f"Wrote {output_path}")
    print(f"Duration: {duration:.2f} seconds")


if __name__ == "__main__":
    main()