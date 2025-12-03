#!/usr/bin/env python3
"""
Generate markdown documentation files for wallpaper categories.

This script scans the docs/classified folder and generates a markdown file
for each subcategory following the format used in space.md.
"""

import os
from pathlib import Path
from typing import List


def get_image_files(directory: Path) -> List[Path]:
    """Get all image files from a directory."""
    image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    image_files = []

    for file_path in directory.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in image_extensions:
            image_files.append(file_path)

    return sorted(image_files)


def create_category_title(category_name: str) -> str:
    """Convert category name to a proper title."""
    # Handle special cases
    if category_name == "uncategorized":
        return "Uncategorized"

    # Capitalize first letter of each word
    return category_name.replace("_", " ").replace("-", " ").title()


def format_filename_to_title(filename: str) -> str:
    """Convert kebab-case filename to proper title format."""
    # Remove extension
    name_without_ext = filename.rsplit(".", 1)[0]

    # Replace hyphens and underscores with spaces, then title case
    title = name_without_ext.replace("-", " ").replace("_", " ")

    # Capitalize each word
    return " ".join(word.capitalize() for word in title.split())


def generate_markdown_content(category: str, image_files: List[Path]) -> str:
    """Generate markdown content for a category."""
    title = create_category_title(category)

    content = "---\nhide:\n    - navigation\n    - toc\n---\n\n"
    content += f"# {title}\n\n"
    content += '<div class="grid cards" markdown>\n\n'

    for image_file in image_files:
        # Use relative path from docs/ directory
        relative_path = f"classified/{category}/{image_file.name}"

        # Convert filename to proper title
        image_title = format_filename_to_title(image_file.name)

        content += f"-   [![{image_title}]({relative_path})]({relative_path})\n\n"
        content += f"    **{image_title}**\n\n"

    content += "</div>\n"

    return content


def main():
    """Main function to generate documentation files."""
    # Define paths
    docs_dir = Path("docs")
    classified_dir = docs_dir / "classified"

    if not classified_dir.exists():
        print(f"Error: {classified_dir} does not exist")
        return

    # Get all category directories
    categories = [d.name for d in classified_dir.iterdir() if d.is_dir()]

    print(f"Found {len(categories)} categories: {', '.join(categories)}")

    for category in categories:
        category_path = classified_dir / category
        image_files = get_image_files(category_path)

        if not image_files:
            print(f"No images found in {category}, skipping...")
            continue

        print(f"Generating {category}.md with {len(image_files)} images...")

        # Generate markdown content
        markdown_content = generate_markdown_content(category, image_files)

        # Write to file
        output_file = docs_dir / f"{category}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        print(f"Created {output_file}")

    print("Documentation generation complete!")


if __name__ == "__main__":
    main()
