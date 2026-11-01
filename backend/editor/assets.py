"""Resolve Vite's hashed build outputs through Django staticfiles."""
import json
from django.contrib.staticfiles import finders
from django.templatetags.static import static

def frontend_assets():
    manifest_path = finders.find("editor/dist/manifest.json")
    if not manifest_path:
        return None
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    styles, visited = [], set()
    def collect(key):
        if key in visited:
            return
        visited.add(key)
        chunk = manifest[key]
        for dependency in chunk.get("imports", []):
            collect(dependency)
        for name in chunk.get("css", []):
            url = static(f"editor/dist/{name}")
            if url not in styles:
                styles.append(url)
    collect("src/main.tsx")
    return {"script": static(f'editor/dist/{manifest["src/main.tsx"]["file"]}'), "styles": styles}
