# Kill processes occupying development ports (Windows PowerShell)

$ports = @(3000, 3001, 8000, 5432, 6379, 9000, 9001)

Write-Host "🔍 Checking for processes on development ports..." -ForegroundColor Cyan

foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    
    if ($connections) {
        foreach ($conn in $connections) {
            $pid = $conn.OwningProcess
            Write-Host "⚠️  Port $port is occupied by PID $pid" -ForegroundColor Yellow
            Write-Host "   Killing process..." -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "✅ Port $port freed" -ForegroundColor Green
        }
    } else {
        Write-Host "✓  Port $port is free" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "✅ All ports checked and cleared" -ForegroundColor Green
