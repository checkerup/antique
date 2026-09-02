# Code Signing for antique

## Current state: unsigned

antique portable builds are **not code-signed**. This means:

- **Windows SmartScreen** will show "Windows protected your PC" on first run.
- Users must click "More info" → "Run anyway" to proceed.
- Antivirus software may flag unsigned executables with higher scrutiny.

This is an intentional choice — we do not pretend code signing exists when
it doesn't. The build scripts explicitly avoid signing-related flags.

## How to enable signing

### Prerequisites

1. Purchase an **EV Code Signing Certificate** from a trusted CA
   (DigiCert, Sectigo, GlobalSign). EV certificates provide immediate
   SmartScreen reputation.
2. Store the certificate in a `.pfx` file or Windows Certificate Store.

### Sign with signtool (Windows SDK)

```bat
signtool sign ^
    /f "C:\path\to\cert.pfx" ^
    /p "CERT_PASSWORD" ^
    /fd SHA256 ^
    /tr http://timestamp.digicert.com ^
    /td SHA256 ^
    dist\antique-portable\antique\antique.exe
```

### Automated signing in CI

Add a GitHub Actions secret `CODE_SIGN_PFX` (base64-encoded) and
`CODE_SIGN_PASSWORD`, then add a signing step after PyInstaller:

```yaml
- name: Sign executable
  if: matrix.os == 'windows-latest'
  run: |
    echo ${{ secrets.CODE_SIGN_PFX }} | base64 -d > cert.pfx
    signtool sign /f cert.pfx /p ${{ secrets.CODE_SIGN_PASSWORD }} \
      /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 \
      dist/antique-portable/antique/antique.exe
```

### SmartScreen reputation

New certificates require reputation building:
- EV certificates get immediate reputation.
- Standard OV certificates require downloads/installs over time.
- Microsoft's [ submission API ](https://www.microsoft.com/en-us/wdsi/filesubmission)
  can accelerate this for signed binaries.
