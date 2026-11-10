"""BIOS / driver update hints.

Linux firmware should be installed through fwupd, not Windows executables.
The ASUS support API is queried read-only so the Updates page can link to
the official download, matching G-Helper's updater role.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request

from ghelper.hw.sysfs import dmi
from ghelper.result import Result


def asus_bios(model: str | None = None, timeout: float = 8) -> Result:
    model = model or dmi("product_name")
    query = model.replace(" ", "")
    url = (
        "https://www.asus.com/support/api/product.asmx/GetPDBIOS"
        "?website=global&model=%s&cpu=" % urllib.request.quote(query)
    )
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        return Result(False, str(exc), {"url": url, "model": model})
    items = payload.get("Result") or payload.get("result") or payload
    return Result(True, "", {"model": model, "url": url, "payload": items})


def fwupd_summary() -> dict:
    if not shutil.which("fwupdmgr"):
        return {"available": False}
    proc = subprocess.run(["fwupdmgr", "get-updates", "--json"], text=True, capture_output=True, timeout=20, check=False)
    return {"available": True, "code": proc.returncode, "stdout": (proc.stdout or "")[:4000], "stderr": (proc.stderr or "")[:1000]}
