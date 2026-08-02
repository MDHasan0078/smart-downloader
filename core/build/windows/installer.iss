; Inno Setup script: Simple YT Downloader (engine) Windows installer.
; Sources resolve relative to the PyInstaller bundle in core/build/dist/engine.
; Build from repo root (CI does this):
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" core/build/windows/installer.iss /DVERSION=1.1.0
;
; BUNDLE/OUTPUT default to paths relative to this script's directory; CI
; overrides them with absolute paths so resolution is unambiguous.
;
; Output: <OUTPUT>/SimpleYTDownloader-<VERSION>-Setup.exe

#ifndef VERSION
  #define VERSION "0.0.0"
#endif
#ifndef BUNDLE
  #define BUNDLE "..\..\dist\engine"
#endif
#ifndef OUTPUT
  #define OUTPUT "..\..\dist"
#endif

#define MyAppName "Simple YT Downloader (Engine)"
#define MyAppPublisher "MD. Mahmudul Hasan"
#define MyAppVersion VERSION

[Setup]
AppId={{B8A9F1D2-4C3E-4A5B-9F0E-2C1D3E4F5A6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\SimpleYTDownloader
DefaultGroupName=Simple YT Downloader
DisableProgramGroupPage=yes
OutputDir={#OUTPUT}
OutputBaseFilename=SimpleYTDownloader-{#MyAppVersion}-Setup
SourceDir={#BUNDLE}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName=Simple YT Downloader (Engine)

[Files]
Source: "engine.exe"; DestDir: "{app}\bin"
Source: "yt-dlp.exe"; DestDir: "{app}\bin"
Source: "ffmpeg.exe"; DestDir: "{app}\bin"
