#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.request import urlopen, Request
from html.parser import HTMLParser

WATERFOX_DOWNLOAD_PAGE = "https://www.waterfox.net/download/"

class WaterfoxDownloadLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.download_url = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = None
        for k, v in attrs:
            if k.lower() == "href":
                href = v
                break
        
        if not href or self.download_url is not None:
            return
        
        if href.lower().endswith(".exe") and "waterfox" in href.lower():
            if href.startswith("http://") or href.startswith("https://"):
                self.download_url = href
            else:
                self.download_url = "https://www.waterfox.net" + href

def _extract_version_from_url(url: str) -> str | None:
    """
    Versucht, die Version aus dem Dateinamen im Link zu ziehen.
    z.B. .../Waterfox%20Setup%206.6.5.1.exe -> 6.6.5.1
    """
    m = re.search(r"(\d+(?:\.\d+)+)(?:\.exe)$", url, re.IGNORECASE)
    if m:
        return m.group(1)
    
    m = re.search(r"(\d+\.\d+\.\d+(?:\.\d+)?)", url)
    if m:
        return m.group(1)
    return None

def _extract_latest_version_from_html(html: str) -> str:
    """
    Versucht robust, eine Versionsnummer aus dem HTML zu extrahieren.
    1. 'Version 6.6.5'
    2. erste 3-teilige Nummer '6.6.5'
    3. fallback: erste 2-teilige Nummer '6.6'
    """
    m = re.search(r"Version\s*([0-9]+(?:\\.[0-9]+)+)", html, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    
    m = re.search(r"([0-9]+\.[0-9]+\.[0-9]+)", html)
    if m:
        return m.group(1).strip()
    
    m = re.search(r"([0-9]+\.[0-9]+)", html)
    if m:
        return m.group(1).strip()
    
    raise RuntimeError("Konnte keine Versionsnummer im HTML finden.")

def fetch_latest_version_and_url() -> tuple[str, str]:
    """
    Lädt die Download-Seite und extrahiert:
    - neueste Version (z.B. '6.6.5')
    - Windows-Installer-URL (.exe)
    """
    print(f"Fetching Waterfox download page: {WATERFOX_DOWNLOAD_PAGE}")
    req = Request(WATERFOX_DOWNLOAD_PAGE, headers={"User-Agent": "Mozilla/5.0"})
    
    with urlopen(req) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    parser = WaterfoxDownloadLinkParser()
    parser.feed(html)
    
    if not parser.download_url:
        raise RuntimeError("Konnte keinen Waterfox-Windows-Download-Link (EXE) finden.")
    
    installer_url = parser.download_url
    print(f"Found installer URL: {installer_url}")

    version_from_url = _extract_version_from_url(installer_url)
    if version_from_url:
        print(f"Extracted version from URL: {version_from_url}")
        return version_from_url, installer_url

    try:
        latest_version = _extract_latest_version_from_html(html)
        print(f"Extracted version from HTML text: {latest_version}")
        return latest_version, installer_url
    except Exception as e:
        raise RuntimeError(f"URL gefunden, aber keine Version ermittelbar: {e}")

def get_installed_version(script_dir: Path) -> str | None:
    glean_db_path = script_dir / "data" / "profile" / "default" / "datareporting" / "glean" / "db" / "data.safe.bin"
    
    if not glean_db_path.is_file():
        print(f"Glean DB not found at: {glean_db_path}")
        print("Cannot determine installed version (application.ini check is disabled).")
        return None

    try:
        with open(glean_db_path, "rb") as f:
            content = f.read()
        
        key = b"glean_client_info#app_display_version"
        start_index = content.find(key)
        
        if start_index == -1:
            print("Glean DB found, but version key 'glean_client_info#app_display_version' not present.")
            return None
        search_window_start = start_index + len(key)
        search_window_end = search_window_start + 60
        chunk = content[search_window_start:search_window_end]
        m = re.search(rb"(\d+\.\d+(\.\d+)?)", chunk)
        if m:
            version_str = m.group(1).decode("utf-8", errors="ignore")
            print(f"Installed Waterfox version (from Glean DB): {version_str}")
            return version_str
            
    except Exception as e:
        print(f"Error reading Glean DB: {e}")
        return None
    
    return None

def parse_version(v: str) -> tuple[int, ...]:
    """
    Wandelt '6.6.5' -> (6, 6, 5) um.
    """
    parts = re.findall(r"\d+", v)
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return ()

def download_to_temp(url: str) -> Path:
    """
    Lädt die Datei unter url nach %TEMP% und gibt den Pfad zurück.
    """
    temp_dir = Path(tempfile.gettempdir())
    filename = url.split("/")[-1] or "waterfox_setup.exe"
    target = temp_dir / filename
    
    print(f"Downloading installer to: {target}")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req) as resp, open(target, "wb") as f:
        shutil.copyfileobj(resp, f)
    return target

def extract_with_7zip(archive: Path, out_dir: Path, seven_zip_exe: Path) -> None:
    """
    Entpackt das übergebene Archiv (EXE/7z/ZIP) mit 7-Zip in out_dir.
    """
    if not seven_zip_exe.is_file():
        raise FileNotFoundError(f"7z.exe wurde nicht gefunden unter: {seven_zip_exe}")
    
    print(f"Extracting with 7-Zip: {archive} -> {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        str(seven_zip_exe),
        "x",
        str(archive),
        f"-o{out_dir}",
        "-y",
    ]
    subprocess.run(cmd, check=True)

def copy_core_to_app(extracted_root: Path, app_dir: Path) -> None:
    """
    Sucht den 'core'-Ordner im entpackten Verzeichnis, löscht 'core/uninstall'
    und kopiert den Inhalt von 'core' in den app-Ordner (mit Überschreiben).
    """
    core_dir = None
    candidate = extracted_root / "core"
    if candidate.is_dir():
        core_dir = candidate
    else:
        for entry in extracted_root.iterdir():
            if entry.is_dir():
                c2 = entry / "core"
                if c2.is_dir():
                    core_dir = c2
                    break
    
    if core_dir is None:
        raise RuntimeError(f"Konnte keinen 'core'-Ordner unter {extracted_root} finden.")
    
    print(f"Found core directory: {core_dir}")
    
    uninstall_dir = core_dir / "uninstall"
    if uninstall_dir.is_dir():
        print(f"Removing uninstall folder: {uninstall_dir}")
        shutil.rmtree(uninstall_dir, ignore_errors=True)
    
    app_dir.mkdir(parents=True, exist_ok=True)
    for item in core_dir.iterdir():
        dest = app_dir / item.name
        if item.is_dir():
            print(f"Copying directory: {item} -> {dest}")
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            print(f"Copying file: {item} -> {dest}")
            shutil.copy2(item, dest)

def main():
    script_dir = Path(__file__).resolve().parent
    app_dir = script_dir / "app"
    seven_zip_exe = script_dir / "7zip" / "7z.exe"
    
    print(f"Script directory : {script_dir}")
    print(f"Target app folder: {app_dir}")
    print(f"Using 7-Zip exe  : {seven_zip_exe}")
    
    installed_version = get_installed_version(script_dir)
    
    latest_version, installer_url = fetch_latest_version_and_url()
    
    if installed_version:
        v_inst = parse_version(installed_version)
        v_latest = parse_version(latest_version)
        
        if v_inst and v_latest and v_inst >= v_latest:
            print(f"Installed version ({installed_version}) is up to date (latest detected: {latest_version}).")
            print("No update necessary; download skipped.")
            return
        else:
            print(f"Update required: {installed_version} -> {latest_version}")
    else:
        print(f"No installed version detected (or DB missing); will install {latest_version} fresh.")
    
    installer_path = download_to_temp(installer_url)

    temp_extract_dir = Path(tempfile.mkdtemp(prefix="waterfox_extract_"))
    try:
        extract_with_7zip(installer_path, temp_extract_dir, seven_zip_exe)
        
        copy_core_to_app(temp_extract_dir, app_dir)
        
        print("Update fertig. Waterfox portable im 'app'-Ordner aktualisiert.")
        
    finally:
        try:
            if temp_extract_dir.is_dir():
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
        except Exception:
            pass

if __name__ == "__main__":
    main()
