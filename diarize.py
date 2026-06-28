#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import torch
from gigaam_mlx import load_model, transcribe
from pyannote.audio import Pipeline

def parse_args():
    parser = argparse.ArgumentParser(
        description="Speaker Diarization CLI using GigaAM-v3 RNNT (MLX) via Diarize-then-Transcribe."
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to the input audio file (e.g., wav, mp3, m4a)."
    )
    parser.add_argument(
        "-o", "--output",
        default="transcript.txt",
        help="Path to save the output text file (default: transcript.txt)."
    )
    parser.add_argument(
        "--token",
        help="Hugging Face API token (can also be set via HF_TOKEN env variable)."
    )
    # Speaker constraints parameters
    parser.add_argument(
        "--min-speakers",
        type=int,
        default=None,
        help="Lower bound on the number of speakers."
    )
    parser.add_argument(
        "--max-speakers",
        type=int,
        default=None,
        help="Upper bound on the number of speakers."
    )
    parser.add_argument(
        "--num-speakers",
        type=int,
        default=None,
        help="Exact number of speakers (overrides min/max constraints if set)."
    )
    return parser.parse_args()

def main():
    args = parse_args()

    # Resolve HF Token
    hf_token = args.token or os.getenv("HF_TOKEN")
    if not hf_token:
        print("Error: Hugging Face token is missing. Pass it via --token or set the HF_TOKEN env variable.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found.", file=sys.stderr)
        sys.exit(1)

    # 1. Load Models
    print("--> Loading GigaAM-v3 RNNT model (MLX)...")
    model, tokenizer = load_model(model_type="rnnt")

    print("--> Loading Speaker Diarization Pipeline...")
    diarize_pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-community-1",
        token=hf_token
    )
    if torch.backends.mps.is_available():
        diarize_pipeline.to(torch.device("mps"))

    # 2. Prepare Diarization Pipeline Arguments
    diarize_kwargs = {}
    if args.num_speakers is not None:
        diarize_kwargs["num_speakers"] = args.num_speakers
        print(f"--> Target configuration: Exactly {args.num_speakers} speakers.")
    else:
        if args.min_speakers is not None:
            diarize_kwargs["min_speakers"] = args.min_speakers
        if args.max_speakers is not None:
            diarize_kwargs["max_speakers"] = args.max_speakers

        if diarize_kwargs:
            constraints = ", ".join([f"{k}: {v}" for k, v in diarize_kwargs.items()])
            print(f"--> Target configuration constraints: {constraints}")

    # 3. Run Diarization First
    print(f"--> Analyzing speaker patterns on: {args.input}")
    diarization_output = diarize_pipeline(args.input, **diarize_kwargs)

    # 4. Process and Transcribe Segments
    print("--> Transcribing speaker segments...")
    print("\n--- Final Diarized Transcript ---")

    with open(args.output, "w", encoding="utf-8") as f:
        for turn, speaker in diarization_output.exclusive_speaker_diarization:
            start_time = turn.start
            end_time = turn.end
            duration = end_time - start_time

            if duration < 0.4:
                continue

            temp_chunk = f"temp_{speaker}_{start_time:.2f}.wav"

            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_time),
                "-to", str(end_time),
                "-i", args.input,
                "-c", "copy",
                temp_chunk
            ]
            subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            try:
                res = transcribe(model, tokenizer, temp_chunk)
                text = res.get("text", "") if isinstance(res, dict) else str(res)
                text = text.strip()

                if text:
                    line = f"[{start_time:.2f}s - {end_time:.2f}s] {speaker}: {text}\n"
                    f.write(line)
                    print(line.strip())

            except Exception as e:
                print(f"Skipping segment [{start_time:.2f}s]: transcription error - {e}", file=sys.stderr)
            finally:
                if os.path.exists(temp_chunk):
                    os.remove(temp_chunk)

    print("\n--> Process Complete! Transcript saved to:", args.output)

if __name__ == "__main__":
    main()
