import os
import sys
import subprocess
import base64

desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
shortcut_path = os.path.join(desktop_path, "台股技術指標篩選器 Web.lnk")
target_folder = os.path.dirname(os.path.abspath(__file__))
script_name = "股票技術指標篩選器_Web.py"

raw_cmd = f"Set-Location -Path '{target_folder}'; python -m streamlit run '{script_name}'"
encoded_cmd = base64.b64encode(raw_cmd.encode('utf-16le')).decode('ascii')

ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
$Shortcut.TargetPath = 'powershell.exe'
$Shortcut.Arguments = '-NoProfile -WindowStyle Hidden -EncodedCommand {encoded_cmd}'
$Shortcut.WorkingDirectory = '{target_folder}'
$Shortcut.Description = '台股技術指標篩選器 Web 版'
$Shortcut.IconLocation = '$env:SystemRoot\\System32\\shell32.dll,14'
$Shortcut.Save()
"""

temp_ps1 = os.path.join(target_folder, "temp_shortcut.ps1")
with open(temp_ps1, "w", encoding="utf-8-sig") as f:
    f.write(ps_script)

try:
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", temp_ps1], check=True)
    print(f"Successfully created desktop shortcut at: {shortcut_path}")
finally:
    if os.path.exists(temp_ps1):
        os.remove(temp_ps1)
