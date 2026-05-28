import os
import sys
import shutil
import urllib.request
import tarfile
import zipfile

def get_java_executable(runtime_dir: str) -> str:
    """
    Downloads and extracts JDK 21 if not already present, and returns the path to the java executable.
    """
    os.makedirs(runtime_dir, exist_ok=True)
    
    # Determine OS and JDK URL
    is_windows = sys.platform.startswith("win")
    
    if is_windows:
        jdk_url = "https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/adoptium?project=jdk"
        jdk_folder_name = "jdk-21"
        java_bin_rel = os.path.join("bin", "java.exe")
    else:
        # Assume Linux x64
        jdk_url = "https://api.adoptium.net/v3/binary/latest/21/ga/linux/x64/jdk/hotspot/normal/adoptium?project=jdk"
        jdk_folder_name = "jdk-21"
        java_bin_rel = os.path.join("bin", "java")

    jdk_dest_dir = os.path.join(runtime_dir, jdk_folder_name)
    
    # We look inside the extracted folder to find the actual bin/java.
    # Adoptium extracts into a subdirectory like jdk-21.0.x+y/ so we need to search recursively or locate the folder.
    java_exe_path = find_java_in_dir(jdk_dest_dir, java_bin_rel)
    if java_exe_path and os.path.exists(java_exe_path):
        return java_exe_path

    # Clean existing directory if corrupted
    if os.path.exists(jdk_dest_dir):
        shutil.rmtree(jdk_dest_dir)
    os.makedirs(jdk_dest_dir, exist_ok=True)

    # Download archive
    archive_name = "jdk21.zip" if is_windows else "jdk21.tar.gz"
    archive_path = os.path.join(runtime_dir, archive_name)
    
    print(f"[*] Downloading JDK 21 from Adoptium...")
    print(f"[*] Source: {jdk_url}")
    
    # Download with simple progress log
    def report_hook(block_num, block_size, total_size):
        read_so_far = block_num * block_size
        if total_size > 0:
            percent = min(100, int(read_so_far * 100 / total_size))
            if block_num % 100 == 0:  # Print every few blocks to avoid spamming
                print(f"[*] Downloading: {percent}% ({read_so_far // (1024*1024)}MB / {total_size // (1024*1024)}MB)", end="\r")
        else:
            if block_num % 100 == 0:
                print(f"[*] Downloading: {read_so_far // (1024*1024)}MB", end="\r")

    try:
        # Request with headers to avoid user-agent blocks
        req = urllib.request.Request(
            jdk_url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response, open(archive_path, 'wb') as out_file:
            total_size = int(response.info().get('Content-Length', -1))
            block_size = 8192
            block_num = 0
            while True:
                data = response.read(block_size)
                if not data:
                    break
                out_file.write(data)
                block_num += 1
                report_hook(block_num, block_size, total_size)
        print("\n[*] Download completed successfully.")
    except Exception as e:
        print(f"\n[!] Failed to download JDK: {e}")
        # Clean archive file if exists
        if os.path.exists(archive_path):
            os.remove(archive_path)
        raise e

    # Extract Archive
    print(f"[*] Extracting JDK 21 archive...")
    try:
        if is_windows:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(jdk_dest_dir)
        else:
            with tarfile.open(archive_path, 'r:gz') as tar_ref:
                tar_ref.extractall(jdk_dest_dir)
        print("[*] Extraction complete.")
    except Exception as e:
        print(f"[!] Extraction failed: {e}")
        raise e
    finally:
        # Clean up archive
        if os.path.exists(archive_path):
            os.remove(archive_path)

    # Find the java binary path in the extracted folder
    java_exe_path = find_java_in_dir(jdk_dest_dir, java_bin_rel)
    if not java_exe_path:
        raise RuntimeError("Could not find java executable in the extracted JDK directory.")
    
    # On linux, make sure java binary has executable permission
    if not is_windows:
        try:
            os.chmod(java_exe_path, 0o755)
        except Exception as e:
            print(f"[!] Warning: Failed to chmod java binary: {e}")

    print(f"[*] Portable JDK 21 ready at: {java_exe_path}")
    return java_exe_path

def find_java_in_dir(base_dir: str, rel_path: str) -> str:
    """
    Adoptium extracts to a subfolder like jdk-21.0.x+y.
    We check one level down for the relative bin/java path.
    """
    if not os.path.exists(base_dir):
        return None
    for entry in os.listdir(base_dir):
        full_entry = os.path.join(base_dir, entry)
        if os.path.isdir(full_entry):
            candidate = os.path.join(full_entry, rel_path)
            if os.path.exists(candidate):
                return candidate
    return None
