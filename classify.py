import argparse
import json
import logging
import os
from pathlib import Path
from typing import Optional, Set
import re
import shutil
import sys

import ollama

# Configure logging with time only (no date)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stderr)],
)

CATEGORIES = [
    "space",
    "anime",
    "landscape",
    "mythological",
    "realistic",
    "uncategorized",
]

CLOUD_MODEL_NAME = "qwen3-vl:235b-cloud"
MODEL_NAME = "qwen3-vl:4b"


def slugify(text: str) -> str:
    """Convert arbitrary text to a safe kebab-case slug."""
    text = text.strip().lower()
    # Replace non-alphanumeric with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Remove leading/trailing hyphens
    text = text.strip("-")
    return text or "unnamed"


def load_processed_images(tracking_file: Path) -> set[str]:
    """
    Load the set of already processed image paths from tracking file.
    """
    if not tracking_file.exists():
        return set()

    try:
        with open(tracking_file, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    except Exception as e:
        logging.warning("Could not load tracking file %s: %s", tracking_file, e)
        return set()


def save_processed_image(tracking_file: Path, image_path: Path) -> None:
    """
    Append a processed image path to the tracking file.
    """
    try:
        with open(tracking_file, "a", encoding="utf-8") as f:
            f.write(f"{image_path.resolve()}\n")
    except Exception as e:
        logging.warning("Could not write to tracking file %s: %s", tracking_file, e)


def create_prompts(image_path: Path) -> tuple[str, str]:
    """
    Create system and user prompts for image classification.
    Returns (system_prompt, user_prompt).
    """
    system_prompt = "You are now an Image Analyser. Your job is to look at images and categorize them into one of the predefined categories. You also should provide a short descriptive name for the image. You must respond with ONLY valid JSON. No explanations, no prose, just JSON."

    user_prompt = f"""
Analyse this image. If you are unsure about the category, choose "uncategorized". Generate a short descriptive name of 3-5 words. 

Categories: {', '.join(CATEGORIES)}

Respond ONLY with this exact JSON format (no other text):
{{"category": "one_from_list", "name": "3-5 word descriptive name"}}

Example valid responses:
{{"category": "anime", "name": "blue eyes with glasses"}}
{{"category": "landscape", "name": "mountain valley sunset"}}

Current filename: {image_path.stem}
"""

    return system_prompt, user_prompt


def call_local_api(image_path: Path, system_prompt: str, user_prompt: str) -> str:
    """
    Call local Ollama model for image classification.
    """
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
                "images": [str(image_path)],
            },
        ],
        options={"temperature": 0.0},
    )
    return response["message"]["content"].strip()


def call_cloud_api(image_path: Path, system_prompt: str, user_prompt: str) -> str:
    """
    Call Ollama cloud model for image classification.
    Uses the same ollama library but with cloud endpoint.
    """
    # Use Ollama cloud endpoint
    client = ollama.Client(
        host="https://ollama.com",
        headers={"Authorization": "Bearer " + os.environ.get("OLLAMA_API_KEY")},
    )

    response = client.chat(
        model=CLOUD_MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
                "images": [str(image_path)],
            },
        ],
        options={"temperature": 0.0},
    )

    return response["message"]["content"].strip()


def classify_and_name(image_path: Path, use_cloud: bool = False):
    """
    Call Ollama model to:
      - Classify the image into one of CATEGORIES
      - Generate a short kebab-case base filename
    Returns (category, name_slug).
    """
    system_prompt, user_prompt = create_prompts(image_path)

    if use_cloud:
        content = call_cloud_api(image_path, system_prompt, user_prompt)
    else:
        content = call_local_api(image_path, system_prompt, user_prompt)

    # Strip markdown code fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove opening fence
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    # Remove any trailing explanatory text after the JSON
    if "}" in content:
        # Find the last closing brace and cut everything after
        last_brace = content.rfind("}")
        content = content[: last_brace + 1]

    # Attempt to parse the model output as JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logging.warning(
            "Failed to parse JSON for %s, content was: %s", image_path, content
        )
        return "uncategorized", slugify(image_path.stem)

    # Handle case where model returns a list instead of a dict
    if isinstance(data, list):
        logging.warning(
            "Model returned a list instead of dict for %s. Content: %s",
            image_path,
            content,
        )
        return "uncategorized", slugify(image_path.stem)

    if not isinstance(data, dict):
        logging.warning(
            "Model returned unexpected type for %s. Content: %s", image_path, content
        )
        return "uncategorized", slugify(image_path.stem)

    raw_category = str(data.get("category", "")).strip().lower()
    if raw_category not in [c.lower() for c in CATEGORIES]:
        category = "uncategorized"
    else:
        # Normalize to the canonical category spelling
        for c in CATEGORIES:
            if c.lower() == raw_category:
                category = c
                break

    raw_name = str(data.get("name", "")).strip()
    if not raw_name:
        name_slug = slugify(image_path.stem)
    else:
        # Enforce 3-5 word limit by truncating if necessary
        words = raw_name.split()
        if len(words) > 5:
            raw_name = " ".join(words[:5])
        name_slug = slugify(raw_name)

    return category, name_slug


def iter_images(path: Path, exclude_dirs: Optional[Set[Path]] = None):
    """Yield image files from a single file or a folder (recursive).

    Optionally skip files located under any directory in exclude_dirs.
    """
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    exclude_dirs = {d.resolve() for d in (exclude_dirs or set())}

    if path.is_file():
        if path.suffix.lower() in exts:
            yield path
    elif path.is_dir():
        for p in path.rglob("*"):
            # Skip anything under excluded directories
            p_resolved = p.resolve()
            if any(p_resolved.is_relative_to(ex) for ex in exclude_dirs):
                continue
            if p.suffix.lower() in exts:
                yield p
    else:
        raise FileNotFoundError(f"Path does not exist: {path}")


def parse_args():
    ap = argparse.ArgumentParser(
        description="Classify images with via local or cloud Ollama models and generate names."
    )
    ap.add_argument(
        "path",
        help="Image file or folder",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("."),
        help="Output folder (default: current working directory) organized by category subdirectories",
    )
    ap.add_argument(
        "-c",
        "--copy",
        action="store_true",
        help="Copy images to output folder organized by category",
    )
    ap.add_argument(
        "-m",
        "--move",
        action="store_true",
        help="Move images to output folder organized by category (instead of copy)",
    )
    ap.add_argument(
        "--cloud",
        action="store_true",
        help="Use Ollama cloud model instead of local instance. API key must be set in OLLAMA_API_KEY environment variable",
    )
    # If invoked with no arguments, show help and exit
    if len(sys.argv) == 1:
        ap.print_help()
        sys.exit(0)

    return ap.parse_args()


def main():
    args = parse_args()

    root = Path(args.path)

    # Validate arguments
    if args.copy and args.move:
        logging.error("Cannot use both --copy and --move at the same time")
        sys.exit(1)

    # Require either --copy or --move when --output is specified
    if args.output and args.output != Path(".") and not args.copy and not args.move:
        logging.error("--output requires either --copy or --move to be specified")
        sys.exit(1)

    # Resolve output directory relative to current working directory (not input path)
    output_dir = None
    if (args.copy or args.move) and args.output:
        output_dir = (
            args.output if args.output.is_absolute() else (Path.cwd() / args.output)
        )

        # Create output directory structure if copying or moving
        output_dir.mkdir(parents=True, exist_ok=True)
        for category in CATEGORIES:
            (output_dir / category).mkdir(exist_ok=True)
        # Create uncategorized folder too
        (output_dir / "uncategorized").mkdir(exist_ok=True)

    results = []

    # Load processed images tracking
    tracking_file = Path("processed_images.txt")
    processed_images = load_processed_images(tracking_file)

    # Exclude logic: if input != output, exclude entire output dir
    # If input == output, exclude the category subdirectories to avoid reprocessing
    exclude = set()
    if output_dir:
        if output_dir.resolve() != root.resolve():
            exclude = {output_dir}
        else:
            # When input == output, exclude category subdirectories
            exclude = {output_dir / category for category in CATEGORIES}
            exclude.add(output_dir / "uncategorized")

    for img in iter_images(root, exclude_dirs=exclude):
        # Skip if already processed
        img_resolved = str(img.resolve())
        if img_resolved in processed_images:
            logging.info("Skipping already processed %s", img)
            continue
        logging.info("Processing %s...", img)
        category, name = classify_and_name(img, use_cloud=args.cloud)
        result = {
            "input_path": str(img),
            "category": category,
            "name": name,
        }
        results.append(result)

        # Track this image as processed
        save_processed_image(tracking_file, img)

        # Copy or move file to output folder if requested
        if (args.copy or args.move) and output_dir:
            # Generate new filename: name_slug + original extension
            new_filename = f"{name}{img.suffix}"
            dest_path = output_dir / category / new_filename

            # Handle filename conflicts
            counter = 1
            while dest_path.exists():
                new_filename = f"{name}-{counter}{img.suffix}"
                dest_path = output_dir / category / new_filename
                counter += 1

            try:
                if args.move:
                    shutil.move(str(img), str(dest_path))
                    logging.info("Moved to %s", dest_path)
                else:
                    shutil.copy2(img, dest_path)
                    logging.info("Copied to %s", dest_path)
            except Exception as e:
                action = "move" if args.move else "copy"
                logging.error("Failed to %s %s: %s", action, img, e)

    # Print results
    for r in results:
        print(f"{r['input_path']} -> category={r['category']}, name={r['name']}")


if __name__ == "__main__":
    main()
