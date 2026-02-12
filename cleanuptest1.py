import sys
import getpass
import winrm
import logging
import textwrap

# ---------------- CONFIG ----------------
DOMAIN_CONTROLLER = "OSSMUE1-OMCDC01.staging.oneds.com"
USERNAME = "svc.rmt.cmp.del@staging.oneds.com"
PORT = 5986
# ----------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def build_script(computer_name):
    return textwrap.dedent(f"""
        param($ComputerName)

        if (-not $ComputerName) {{
            Write-Error "ComputerName is empty"
            exit 1
        }}

        Import-Module ActiveDirectory -ErrorAction Stop

        try {{
            $Computer = Get-ADComputer -Identity $ComputerName -Properties * -ErrorAction Stop
        }} catch {{
            Write-Error "Computer object '$ComputerName' not found."
            exit 2
        }}

        Write-Output "Computer Found:"
        Write-Output "Name: $($Computer.Name)"
        Write-Output "SID: $($Computer.SID)"
        Write-Output "ObjectGUID: $($Computer.ObjectGUID)"
        Write-Output "DN: $($Computer.DistinguishedName)"

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
        Write-Output "`nSUCCESS: Computer '$ComputerName' deleted."
    """)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 cleanup_ad.py <COMPUTER_NAME>")
        sys.exit(1)

    computer_name = sys.argv[1]

    password = getpass.getpass("Enter AD Password: ")

    session = winrm.Session(
        target=f"https://{DOMAIN_CONTROLLER}:{PORT}/wsman",
        auth=(USERNAME, password),
        transport="ntlm",
        server_cert_validation="ignore"
    )

    script = build_script(computer_name)

    logger.info("Connecting to %s", DOMAIN_CONTROLLER)
    result = session.run_ps(script)   # ✅ FIXED

    if result.std_out:
        print(result.std_out.decode())

    if result.std_err:
        print("ERROR:")
        print(result.std_err.decode())
        sys.exit(1)


if __name__ == "__main__":
    main()