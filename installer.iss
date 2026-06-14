; Inno Setup — 千川视频工具箱 v3.1

[Setup]
AppName=千川视频工具箱
AppVersion=3.1
AppPublisher=千川团队
DefaultDirName={userpf}\千川视频工具箱
DefaultGroupName=千川视频工具箱
OutputDir=Output
OutputBaseFilename=千川视频工具箱_Setup
Compression=lzma2
SolidCompression=yes
Uninstallable=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

[Files]
Source: "dist\千川视频工具箱.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\千川视频工具箱"; Filename: "{app}\千川视频工具箱.exe"
Name: "{group}\卸载"; Filename: "{uninstallexe}"
