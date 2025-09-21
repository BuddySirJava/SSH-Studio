; NSIS installer script for SSH Studio
!define AppName "${AppName}"
!define AppVersion "${Version}"
!define CompanyName "BuddySirJava"
!define InstallDir "$PROGRAMFILES\${AppName}"

OutFile "installer\${AppName}-${Version}-Setup.exe"
InstallDir "${InstallDir}"
ShowInstDetails show

RequestExecutionLevel admin

Page directory
Page instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "${SourceDir}\*"

  ; Create a hidden VBS launcher to avoid console window flicker
  FileOpen $0 "$INSTDIR\${AppName}.vbs" w
  FileWrite $0 "Set oShell = CreateObject(\"WScript.Shell\")\r\n"
  FileWrite $0 "oShell.Run Chr(34) & \"$INSTDIR\\SSH-Studio (MSYS2).bat\" & Chr(34), 0\r\n"
  FileClose $0

  ; Create Start Menu folder
  CreateDirectory "$SMPROGRAMS\${AppName}"

  ; Create shortcuts pointing to the VBS (no console)
  CreateShortCut "$DESKTOP\${AppName}.lnk" "$INSTDIR\${AppName}.vbs"
  CreateShortCut "$SMPROGRAMS\${AppName}\${AppName}.lnk" "$INSTDIR\${AppName}.vbs"
SectionEnd

Section -Post
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${AppName}" "DisplayName" "${AppName}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${AppName}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${AppName}" "DisplayVersion" "${AppVersion}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${AppName}" "Publisher" "${CompanyName}"
  CreateShortCut "$SMPROGRAMS\${AppName}\Uninstall ${AppName}.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${AppName}"
  RMDir /r "$SMPROGRAMS\${AppName}"
SectionEnd


