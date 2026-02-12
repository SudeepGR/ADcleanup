import sys
import getpass
import winrm
import logging
import textwrap

# ---------------- CONFIG ----------------
DOMAIN_CONTROLLER = "100.102.10.68"   # Using IP instead of FQDN
USERNAME = "svc.rmt.cmp.del@staging.oneds.com"
PORT = 5986
# ----------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def build_script(computer_name):
    return textwrap.dedent(f"""
        Import-Module ActiveDirectory -ErrorAction Stop

        try {{
            $Computer = Get-ADComputer -Identity "{computer_name}" -Properties * -ErrorAction Stop
        }} catch {{
            Write-Error "Computer object '{computer_name}' not found."
            exit 2
        }}

        Write-Output "Computer Found:"
        Write-Output "Name: $($Computer.Name)"
        Write-Output "SID: $($Computer.SID)"
        Write-Output "ObjectGUID: $($Computer.ObjectGUID)"
        Write-Output "DistinguishedName: $($Computer.DistinguishedName)"

        Write-Output "`nGroup Membership:"
        Get-ADPrincipalGroupMembership -Identity $Computer |
            Select-Object -ExpandProperty Name

        $recycleBinStatus = (Get-ADOptionalFeature -Filter 'Name -like "Recycle Bin Feature"').EnabledScopes

        if ($recycleBinStatus.Count -gt 0) {{
            Write-Output "`nAD Recycle Bin is ENABLED."
        }} else {{
            Write-Error "AD Recycle Bin is NOT enabled. Aborting."
            exit 3
        }}

        Remove-ADComputer -Identity $Computer.DistinguishedName -Confirm:$false
        Write-Output "`nSUCCESS: Computer '{computer_name}' deleted."
    """)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 cleanuptest_ip.py <COMPUTER_NAME>")
        sys.exit(1)

    computer_name = sys.argv[1]

    password = getpass.getpass("Enter AD Password: ")

    logger.info("Connecting to %s", DOMAIN_CONTROLLER)

    try:
        session = winrm.Session(
            target=f"https://{DOMAIN_CONTROLLER}:{PORT}/wsman",
            auth=(USERNAME, password),
            transport="ntlm",
            server_cert_validation="ignore"
        )

        script = build_script(computer_name)

        result = session.run_ps(script)

    except Exception as e:
        logger.error("Connection failed: %s", e)
        sys.exit(1)

    if result.std_out:
        print(result.std_out.decode())

    if result.std_err:
        print("ERROR:")
        print(result.std_err.decode())
        sys.exit(1)


if __name__ == "__main__":
    main()