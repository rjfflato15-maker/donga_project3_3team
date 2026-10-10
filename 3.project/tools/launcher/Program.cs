using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

// Small Windows entry point; app/runtime/models remain in their existing places.
internal static class Program
{
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AttachConsole(uint processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AllocConsole();

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBox(IntPtr owner, string text, string caption, uint type);

    private static bool NeedsConsole(string[] args)
    {
        return args.Length > 0 && (args[0] == "manage" || args[0] == "setup" || args[0] == "setup-ai");
    }

    private static void PrepareCommandConsole(bool interactive)
    {
        // Keep explicit CLI commands usable in a terminal. Only requested management
        // and setup commands may create a console when opened from a shortcut.
        bool attached = AttachConsole(unchecked((uint)-1));
        if (!attached && interactive) attached = AllocConsole();
        // Setup/uninstall invokes stop with no console or standard handles.
        // Changing console encodings in that case throws before Python can stop the server.
        if (attached)
        {
            Console.OutputEncoding = new UTF8Encoding(false);
            Console.InputEncoding = new UTF8Encoding(false);
        }
    }

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

    private static int Run(string root, string[] args, bool interactive, bool forwardOutput, out string errors)
    {
        string python = Path.Combine(root, "backend", ".venv", "Scripts", "python.exe");
        string bundled = Path.Combine(root, "runtime", "python", "python.exe");
        if (File.Exists(bundled)) python = bundled;
        string script = Path.Combine(root, "backend", "pilot_launcher.py");
        if (!File.Exists(script)) throw new InvalidOperationException("앱 폴더 안의 실행 파일을 사용하세요. EXE만 따로 옮기면 실행되지 않습니다.");
        bool installed = File.Exists(python);
        var command = new StringBuilder(installed ? "-X utf8 " : "-3.12 -X utf8 ");
        command.Append(Quote(script));
        foreach (string arg in args) { command.Append(' '); command.Append(Quote(arg)); }
        var info = new ProcessStartInfo(installed ? python : "py.exe", command.ToString());
        info.WorkingDirectory = root;
        info.UseShellExecute = false;
        info.CreateNoWindow = !interactive;
        var errorText = new StringBuilder();
        if (!interactive)
        {
            info.RedirectStandardInput = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            info.StandardOutputEncoding = Encoding.UTF8;
            info.StandardErrorEncoding = Encoding.UTF8;
        }
        using (var process = new Process())
        {
            process.StartInfo = info;
            if (!interactive)
            {
                process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs line)
                {
                    if (line.Data != null && forwardOutput) Console.WriteLine(line.Data);
                };
                process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs line)
                {
                    if (line.Data == null) return;
                    errorText.AppendLine(line.Data);
                    if (forwardOutput) Console.Error.WriteLine(line.Data);
                };
            }
            process.Start();
            if (!interactive)
            {
                process.StandardInput.Close();
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
            }
            process.WaitForExit();
            errors = errorText.ToString().Trim();
            return process.ExitCode;
        }
    }

    private static void ShowStartError(string detail)
    {
        if (detail.Length > 1200) detail = detail.Substring(0, 1200) + "…";
        MessageBox(IntPtr.Zero, "앱을 시작하지 못했습니다.\n\n" + detail
            + "\n\n실행 환경·업무함·서버 상태는 관리 메뉴에서 확인할 수 있습니다.\nC-Pilot.exe manage",
            "C-Pilot 실행 오류", 0x10);
    }

    [STAThread]
    private static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        try
        {
            string errors;
            if (args.Length > 0)
            {
                bool interactive = NeedsConsole(args);
                PrepareCommandConsole(interactive);
                return Run(root, args, interactive, true, out errors);
            }

            // Double-click starts the app silently; the Python entry point opens the browser.
            int result = Run(root, new string[] { "start" }, false, false, out errors);
            if (result != 0) ShowStartError(errors.Length > 0 ? errors : "실행 환경과 앱 설정을 확인하세요.");
            return result;
        }
        catch (Exception error)
        {
            var native = error as System.ComponentModel.Win32Exception;
            string detail = error is InvalidOperationException ? error.Message
                : "앱 폴더와 Python 실행 환경을 확인하세요.\n오류 종류: " + error.GetType().Name
                    + (native == null ? "" : " / Windows " + native.NativeErrorCode);
            if (args.Length == 0) ShowStartError(detail);
            else Console.Error.WriteLine(detail);
            return 1;
        }
    }
}
