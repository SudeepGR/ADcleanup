import os
import sys
import textwrap
import winrm
import logging
from typing import List

logger = logging.getLogger(__name__)


# ---------------- CONFIG ----------------
REMOTE_DOMAIN = "dev.oneds.com"
DOMAIN_CONTROLLER = "dev.oneds.com"  # DC FQDN
USERNAME = os.getenv("AD_USERNAME")
PASSWORD = os.getenv("AD_PASSWORD")
# --------------------------------------


def _build_powershell_script(computer_name: str) -> str:
    return textwrap.dedent(f"""
        Import-Module ActiveDirectory -ErrorAction Stop

        try {{
            $computer = Get-ADComputer -Identity "{computer_name}" -Properties DistinguishedName
        }} catch {{
            Write-Error "Computer object '{computer_name}' not found."
            exit 2
        }}

        $recycleBin = Get-ADOptionalFeature -Filter 'Name -like "Recycle Bin Feature"'

        if (-not $recycleBin.EnabledScopes -or $recycleBin.EnabledScopes.Count -eq 0) {{
            Write-Error "AD Recycle Bin is NOT enabled. Aborting."
            exit 3
        }}

        try {{
            Remove-ADComputer -Identity $computer.DistinguishedName -Confirm:$false
            Write-Output "SUCCESS: Deleted AD computer object '{computer_name}'"
        }} catch {{
            Write-Error "Failed to delete '{computer_name}': $_"
            exit 4
        }}
    """)


def delete_ad_computers(computer_names: List[str]) -> None:
    """
    Deletes AD computer objects safely.
    Intended to be called from main AWS decommission workflow.
    """

    if not USERNAME or not PASSWORD:
        raise RuntimeError("AD_USERNAME or AD_PASSWORD environment variables not set")

    logger.info("Starting AD cleanup for computers: %s", computer_names)

    try:
        session = winrm.Session(
            target=f"https://{DOMAIN_CONTROLLER}:5986/wsman",
            auth=(USERNAME, PASSWORD),
            transport="ntlm",
            server_cert_validation="ignore"
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to establish WinRM session: {exc}") from exc

    for computer in computer_names:
        logger.info("Deleting AD computer object: %s", computer)

        ps_script = _build_powershell_script(computer)
        result = session.run_ps(ps_script)

        if result.std_out:
            logger.info(result.std_out.decode(errors="ignore"))

        if result.std_err:
            logger.error(result.std_err.decode(errors="ignore"))
            raise RuntimeError(f"AD deletion failed for {computer}")

    logger.info("AD cleanup completed successfully.")
 
