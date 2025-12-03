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

## Helper Script: classify.py

`classify.py` is an AI-powered helper script that uses vision models to automatically:

- **Classify images** into predefined categories (space, anime, landscape, mythological, realistic, etc.)
- **Generate descriptive names** - short 3–5 word names in kebab-case format
- **Organize files** - optionally copy or move images into category-based folders
- **Skip processed images** - tracks previously processed files to avoid reprocessing
- **Support multiple backends** - works with local Ollama or cloud Ollama models

> **Model Support**: Tested with `qwen3-vl:4b` on a machine with 12 GB RAM and 6 GB VRAM. The script now supports both local and cloud Ollama instances. Other Ollama vision models may work depending on VRAM/RAM and compatibility.

### Prerequisites

- Install and run [Ollama](https://ollama.com)
- Pull a compatible vision model (e.g. `qwen3-vl:4b`):
```bash
ollama pull qwen3-vl:4b
```

- Install required Python packages:
```bash
pip install ollama
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

**Smart Processing Features:**

- **Automatic resume**: Previously processed images are tracked in `processed_images.txt` and skipped on subsequent runs
- **Conflict resolution**: If two files resolve to the same name, numeric suffixes are added (e.g. `name-1.jpg`)
- **Directory exclusion**: When organizing within the same folder, category subdirectories are automatically excluded from processing

### Cloud Model Support

Use Ollama cloud models instead of local processing. Requires an API key from [Ollama Cloud](https://docs.ollama.com/cloud):

```bash
# Export your Ollama API key first
export OLLAMA_API_KEY="your-api-key-here"

# Use cloud model for faster processing (requires network)
python classify.py rwallpapers4/ -o sorted_wallpapers -c --cloud
```

See [Ollama Cloud Documentation](https://docs.ollama.com/cloud) for more information on obtaining and using API keys.

### Options

- `path` (positional): image file or folder to process
- `-o, --output` (optional): output root folder (default: current directory)
- `-c, --copy` (required if --output is specified): copy images into category subfolders under the output root
- `-m, --move` (required if --output is specified): move images into category subfolders under the output root
- `--cloud` (optional): use Ollama cloud vision model instead of local instance

### Notes

- **Logging**: INFO/WARN/ERROR messages print with timestamps to stderr; results print to stdout
- **Naming**: Generated names are limited to 3–5 words and converted to kebab-case format
- **Processing tracking**: Creates `processed_images.txt` to track completed files and enable resume functionality
- **Model flexibility**: Configure local and cloud model names via `MODEL_NAME` and `CLOUD_MODEL_NAME` variables
- **Performance**: Tested with `qwen3-vl:4b` on 12GB RAM. Cloud models may provide faster processing depending on network vs local hardware performance

## Contributing

> **Note**: Ensure that all contributed images are properly licensed for use and distribution.

1. Clone the repository and navigate to the project directory.
2. Make sure the local Ollama instance is active and has the required vision model pulled (e.g. `qwen3-vl:4b`) if using local processing.
3. Obtain an Ollama Cloud API key if you prefer to use cloud processing and export it as an environment variable:
   ```bash
   export OLLAMA_API_KEY="your-api-key-here"
   ```
4. Add new wallpaper images to a `dump/` folder.
5. Run the classify script to organize and rename the new images:
   ```bash
   python classify.py dump/ -o classified/ -c
   ```
6. Review the `classified/` folder and commit the changes.
7. Submit a pull request with the new images added to the `classified/` folder.

> Code changes to the helper script `classify.py` are also welcome!
