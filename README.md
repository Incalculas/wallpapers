# Wallpapers

Collection of wallpapers I use.

## RWall

Check out [**RWall**](https://github.com/KingBenny101/rwall) - an app designed to easily manage this wallpaper collection. It provides a simple interface to browse, organize, and set wallpapers from this repository.

## Sources

- **rwallpapers**: Top posts of all time from [r/wallpapers](https://reddit.com/r/wallpapers)
- **yourname**: [Your Name movie wallpapers](https://www.flickr.com/photos/147283717@N03/albums/72157705986107921)

## Download

Clone the repository using:

```bash
git clone https://github.com/Incalculas/wallpapers.git
```

## classify.py Usage

`classify.py` is a helper script that uses an Ollama vision model to:

- Classify images into predefined categories
- Generate a short 3–5 word descriptive name (kebab-case)
- Optionally copy or move images into category-based folders

> Tested with `llama3.2-vision` on a machine with 12 GB RAM and 6 GB VRAM. Other Ollama vision models may or may not work depending on VRAM/RAM and compatibility.

### Prerequisites

- Install and run [Ollama](https://ollama.com)
- Pull a compatible vision model (e.g. `llama3.2-vision`):

```bash
ollama pull llama3.2-vision
```

### Basic classification

Process a single image or all images in a folder (recursively):

```bash
# Single image
python classify.py rwallpapers4/bliss.jpg

# Folder (recursive)
python classify.py rwallpapers4/
```

### Copy or move into organized output folders

By default, the output root is the current working directory. Use `-o` to set a target folder.

```bash
# Copy into ./sorted_wallpapers/<category>/
python classify.py rwallpapers4/ -o sorted_wallpapers -c

# Move instead of copy
python classify.py rwallpapers4/ -o sorted_wallpapers -m
```

If two files resolve to the same name, the script appends a numeric suffix (e.g. `name-1.jpg`).

### Options

- `path` (positional): image file or folder to process
- `-o, --output` (optional): output root folder (default: current directory)
- `-c, --copy` (required if --output is specified): copy images into category subfolders under the output root
- `-m, --move` (required if --output is specified): move images into category subfolders under the output root

### Notes

- Logs (INFO/WARN/ERROR) print with timestamps to stderr; results print to stdout.
- Generated names are limited to 3–5 words and converted to kebab-case.
- Tested with `llama3.2-vision` on a machine with 12 GB RAM. Other Ollama vision models may or may not work depending on VRAM/RAM and compatibility.
