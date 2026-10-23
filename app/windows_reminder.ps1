param(
 [Parameter(Mandatory=$true)][ValidateSet('install','remove','status','notify')][string]$Operation,
 [Parameter(Mandatory=$true)][string]$AppId,
 [Parameter(Mandatory=$true)][string]$TaskName,
 [string]$Executable='', [string]$Arguments='', [string]$StartBoundary='', [string]$EndBoundary='',
 [string]$Launch='', [string]$Title='', [string]$Body='', [string]$Tag=''
)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
function TaskStatus {
 $task=Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
 if(-not $task){return @{registered=$false;task_name=$TaskName}}
 $info=Get-ScheduledTaskInfo -TaskName $TaskName
 return @{registered=$true;task_name=$TaskName;state=[string]$task.State;start_boundary=[string]$task.Triggers[0].StartBoundary;next_run=$info.NextRunTime.ToString('yyyy-MM-ddTHH:mm:sszzz');executable=[string]$task.Actions[0].Execute;arguments=[string]$task.Actions[0].Arguments;last_result=$info.LastTaskResult}
}
if($Operation -eq 'install') {
 $trigger=New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours(20).AddMinutes(30))
 $trigger.StartBoundary=$StartBoundary
 if($EndBoundary){$trigger.EndBoundary=$EndBoundary}
 $action=New-ScheduledTaskAction -Execute $Executable -Argument $Arguments -WorkingDirectory (Split-Path -Parent $Executable)
 $settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
 $principal=New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
 Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'StudyForge local Windows study reminder. No GPT, network or background model calls.' -Force | Out-Null
 TaskStatus | ConvertTo-Json -Compress;exit 0
}
if($Operation -eq 'remove') {
 if(Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue){Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false}
 @{removed=$true;task_name=$TaskName}|ConvertTo-Json -Compress;exit 0
}
if($Operation -eq 'status'){TaskStatus|ConvertTo-Json -Compress;exit 0}
[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]|Out-Null
[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,ContentType=WindowsRuntime]|Out-Null
$notifier=[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($AppId)
try{$setting=[string]$notifier.get_Setting()}catch{$setting='NotYetRegistered'}
if($setting -ne 'Enabled' -and $setting -ne 'NotYetRegistered'){@{accepted=$false;notification_setting=$setting;history_present=$false}|ConvertTo-Json -Compress;exit 0}
function Escape([string]$Value){return [System.Security.SecurityElement]::Escape($Value)}
$xml=New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml(('<toast activationType="protocol" launch="{0}" duration="short"><visual><binding template="ToastGeneric"><text>{1}</text><text>{2}</text></binding></visual><audio silent="true"/></toast>' -f (Escape $Launch),(Escape $Title),(Escape $Body)))
$toast=[Windows.UI.Notifications.ToastNotification]::new($xml)
$toast.Tag=$Tag;$toast.Group='StudyForge';$toast.ExpirationTime=[DateTimeOffset]::Now.AddHours(2)
$notifier.Show($toast)
try{$setting=[string]$notifier.get_Setting()}catch{$setting='Unknown'}
Start-Sleep -Milliseconds 600
$present=@([Windows.UI.Notifications.ToastNotificationManager]::History.GetHistory($AppId)|Where-Object {$_.Tag -eq $Tag -and $_.Group -eq 'StudyForge'}).Count -gt 0
@{accepted=$true;notification_setting=$setting;history_present=$present;tag=$Tag}|ConvertTo-Json -Compress
