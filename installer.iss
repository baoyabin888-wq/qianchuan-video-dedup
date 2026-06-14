; Inno Setup — 电商工具箱
; 环境检查 + 安装

[Setup]
AppName=电商工具箱
AppVersion=3.2
AppPublisher=电商工具箱
DefaultDirName={userpf}\电商工具箱
DefaultGroupName=电商工具箱
OutputDir=Output
OutputBaseFilename=电商工具箱_Setup
Compression=lzma2
SolidCompression=yes
Uninstallable=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
; 最小 Windows 版本: Windows 10 (10.0)
MinVersion=10.0

[Files]
Source: "dist\电商工具箱.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\电商工具箱"; Filename: "{app}\电商工具箱.exe"
Name: "{group}\卸载"; Filename: "{uninstallexe}"

[Code]
function InitializeSetup: Boolean;
var
  FreeSpace: Int64;
  Path: String;
  WinVer: TWindowsVersion;
begin
  Result := True;

  // ── 1. 检查系统版本 ──
  GetWindowsVersionEx(WinVer);
  if (WinVer.Major < 10) then
  begin
    MsgBox('错误：需要 Windows 10 或更高版本。' + #13#10 +
           '当前系统: Windows ' + IntToStr(WinVer.Major) + '.' + IntToStr(WinVer.Minor),
           mbCriticalError, MB_OK);
    Result := False;
    Exit;
  end;

  // ── 2. 检查磁盘空间（至少 500MB） ──
  Path := ExpandConstant('{userpf}');
  if GetSpaceOnDisk64(Path, FreeSpace) then
  begin
    if FreeSpace < 524288000 then  { 500 MB }
    begin
      if MsgBox('警告：安装盘剩余空间不足 500MB，可能导致安装失败。' + #13#10 +
                 '当前剩余: ' + FormatFloat('#,### MB', FreeSpace / 1048576.0) + #13#10#13#10 +
                 '是否继续安装？', mbConfirmation, MB_YESNO) = IDNO then
      begin
        Result := False;
        Exit;
      end;
    end;
  end;

  // ── 3. 提示 FFmpeg ──
  if not FileExists(ExpandConstant('{sys}\ffmpeg.exe')) then
  begin
    MsgBox('提示：未检测到系统 FFmpeg。' + #13#10#13#10 +
           '视频去重和下载功能需要 FFmpeg。' + #13#10 +
           '安装完成后请手动下载 ffmpeg.exe 放到安装目录。',
           mbInformation, MB_OK);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // 安装完成后创建桌面快捷方式提示
    MsgBox('安装完成！' + #13#10#13#10 +
           '• 首次使用需注册账号' + #13#10 +
           '• AI生图需在设置页配置 API Key' + #13#10 +
           '• 视频去重需 FFmpeg（如未安装请下载 ffmpeg.exe 放入安装目录）',
           mbInformation, MB_OK);
  end;
end;
