using System;
using System.Diagnostics;
using System.IO;
using System.Text;

// Small Windows entry point; app/runtime/models remain in their existing places.
internal static class Program
{
    private static string Quote(string value)
    {
        var output = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in value)
        {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') { output.Append('\\', slashes * 2 + 1); output.Append(c); }
            else { output.Append('\\', slashes); output.Append(c); }
            slashes = 0;
        }
        output.Append('\\', slashes * 2);
        output.Append('"');
        return output.ToString();
    }

    private static int Run(string root, string[] args)
    {
        string python = Path.Combine(root, "backend", ".venv", "Scripts", "python.exe");
        string script = Path.Combine(root, "backend", "pilot_launcher.py");
        if (!File.Exists(script)) throw new InvalidOperationException("앱 폴더 안의 실행 파일을 사용하세요. EXE만 따로 옮기면 실행되지 않습니다.");
        bool installed = File.Exists(python);
        var command = new StringBuilder(installed ? "-X utf8 " : "-3.12 -X utf8 ");
        command.Append(Quote(script));
        foreach (string arg in args) { command.Append(' '); command.Append(Quote(arg)); }
        var info = new ProcessStartInfo(installed ? python : "py.exe", command.ToString());
        info.WorkingDirectory = root;
        info.UseShellExecute = false;
        using (var process = Process.Start(info))
        {
            process.WaitForExit();
            return process.ExitCode;
        }
    }

    private static int Main(string[] args)
    {
        Console.OutputEncoding = new UTF8Encoding(false);
        Console.InputEncoding = new UTF8Encoding(false);
        string root = AppDomain.CurrentDomain.BaseDirectory;
        try
        {
            // Explicit arguments are non-interactive (including scheduled tasks).
            if (args.Length > 0) return Run(root, args);
            Console.WriteLine("계약 검수 앱을 준비합니다...");
            int result = Run(root, new string[] { "start" });
            if (result != 0)
            {
                Console.WriteLine("처음 준비하거나 설정을 확인할 수 있도록 관리 메뉴를 엽니다.");
                return Run(root, new string[] { "manage" });
            }
            Console.WriteLine("앱을 열었습니다. 관리 메뉴는 M, 실행 창 닫기는 Enter입니다.");
            string answer = Console.ReadLine();
            return String.Equals(answer, "m", StringComparison.OrdinalIgnoreCase)
                ? Run(root, new string[] { "manage" }) : 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine("실행할 수 없습니다. 앱 폴더와 Python 3.12 설치 상태를 확인하세요.");
            var native = error as System.ComponentModel.Win32Exception;
            Console.Error.WriteLine("오류 종류: " + error.GetType().Name + (native == null ? "" : " / Windows " + native.NativeErrorCode));
            if (args.Length == 0) { Console.WriteLine("Enter를 누르면 닫습니다."); Console.ReadLine(); }
            return 1;
        }
    }
}
