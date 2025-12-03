import argparse
import json
import logging
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

MODEL_NAME = "llama3.2-vision"


def slugify(text: str) -> str:
    """Convert arbitrary text to a safe kebab-case slug."""
    text = text.strip().lower()
    # Replace non-alphanumeric with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Remove leading/trailing hyphens
    text = text.strip("-")
    return text or "unnamed"


def classify_and_name(image_path: Path):
    """
    Call Llama 3.2-Vision via Ollama to:
      - Classify the image into one of CATEGORIES
      - Generate a short kebab-case base filename
    Returns (category, name_slug).
    """
    system_prompt = (
        "You must respond with ONLY valid JSON. No explanations, no prose, just JSON."
    )

    user_prompt = f"""
Classify this image.

Categories: {', '.join(CATEGORIES)}

Respond ONLY with this exact JSON format (no other text):
{{"category": "one_from_list", "name": "3-5 word description"}}

Example valid responses:
{{"category": "anime", "name": "blue eyes with glasses"}}
{{"category": "landscape", "name": "mountain valley sunset"}}

Current filename: {image_path.stem}
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
    )

    content = response["message"]["content"].strip()

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
        description="Classify images with Llama 3.2-Vision via Ollama and generate names."
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
        logging.info("Processing %s...", img)
        category, name = classify_and_name(img)
        result = {
            "input_path": str(img),
            "category": category,
            "name": name,
        }
        results.append(result)

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
