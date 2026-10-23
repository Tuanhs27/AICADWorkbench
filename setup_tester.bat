@echo off
chcp 65001 >nul
echo =====================================================================
echo    CÀI ĐẶT AICAD WORKBENCH CHO TESTER / NGƯỜI ĐÁNH GIÁ
echo =====================================================================
echo.

set TARGET_DIR=%APPDATA%\FreeCAD\v1-1\Mod\AICADWorkbench
echo [1/3] Đang sao chép mã nguồn Addon vào FreeCAD...
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
xcopy /E /I /Y "%~dp0\*" "%TARGET_DIR%\" >nul
echo [+] Đã cài đặt xong Addon vào: %TARGET_DIR%
echo.

echo [2/3] Kiểm tra mô hình AI (Ollama)...
where ollama >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [!] Máy chưa cài đặt Ollama. Hãy tải Ollama tại https://ollama.com
    goto finish
)

if exist "%~dp0\Qwen2.5-Coder-3B-Instruct.Q4_K_M.gguf" (
    echo [*] Tìm thấy file mô hình GGUF, đang nạp vào Ollama...
    (
        echo FROM "%~dp0\Qwen2.5-Coder-3B-Instruct.Q4_K_M.gguf"
        echo PARAMETER temperature 0.2
        echo PARAMETER stop "<|im_end|>"
    ) > "%~dp0\Modelfile"
    ollama create cadquery-ai -f "%~dp0\Modelfile"
    echo [+] Đã đăng ký mô hình 'cadquery-ai' vào Ollama thành công!
) else (
    echo [*] Không tìm thấy file GGUF trong thư mục này. 
    echo [*] Nếu Tester chưa có file GGUF, có thể dùng tạm model nền:
    echo     ollama run qwen2.5-coder:3b
)
echo.

echo [3/3] Hoàn tất!
echo Hãy mở FreeCAD 1.1 lên:
echo  1. Chọn Workbench "AI CAD"
echo  2. Bấm nút "Mở Bảng AI Text-to-CAD"
echo  3. Nhập câu prompt kiểm thử và bấm "Tạo mô hình 3D"
echo.
:finish
pause

