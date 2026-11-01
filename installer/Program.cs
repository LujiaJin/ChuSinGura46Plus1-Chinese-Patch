// ChuSinGura46+1 (Steam) 简体中文汉化补丁安装器
// Copyright © 2026 Jin Lujia. 本补丁安装器及构建工具版权归 Jin Lujia 所有。
// 游戏本体及其素材版权归 Inre 所有，本程序仅供持有正版游戏的个人学习交流使用。
// - 自动定位 Steam 安装目录 (AppID 464780)
// - 校验原版文件 SHA256（仅支持当前 Steam 构建，版本不符会拒绝并提示）
// - 安装前自动备份，可一键恢复原版
// - 补丁以差分方式应用，产物与实测通过的汉化文件字节一致
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

namespace ChuSinGura46Plus1ZhPatch
{
    internal static class Program
    {
        private const uint AppId = 464780;
        private const string ExeName = "ChuSinGura46+1.exe";
        public const string DataDir = "ChuSinGura46+1_Data";
        private const string ResName = "resources.assets";
        private const string DllName = "Assembly-CSharp.dll";
        private const string BackupSuffix = ".zh-backup";

        private static readonly string ResOrig = "9F0E61C97F8BE4501F24989292F6327DCDB992A3A9BA1FD392889D6762FF24E5";
        private static readonly string ResNew = "913619615A864D3E185095B9F0AF5EEC9F78CD668CBE7FAF7E70BE2F212814FE";
        private static readonly string DllOrig = "5CCEAA7B13ECD0E551580FE2A463C0559C15E2E0A622B802D64E0DF7ACF56176";
        private static readonly string DllNew = "A9EB1755A402A354C8579C484E5100F33F056E93B17BF1C2BD9EBD0F5B6C3218";

        [STAThread]
        private static int Main(string[] args)
        {
            string dir = null, log = null;
            bool cliInstall = false, cliRestore = false, cliState = false;
            for (int i = 0; i < args.Length; i++)
            {
                switch (args[i])
                {
                    case "--dir": dir = args[++i]; break;
                    case "--log": log = args[++i]; break;
                    case "--install": cliInstall = true; break;
                    case "--restore": cliRestore = true; break;
                    case "--state": cliState = true; break;
                }
            }
            if (cliInstall || cliRestore || cliState)
                return RunCli(dir, cliInstall, cliRestore, cliState, log);

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm(dir));
            return 0;
        }

        // ---------------- locating the game ----------------
        public static List<string> FindGameDirs()
        {
            var found = new List<string>();
            var libs = new List<string>();
            try
            {
                using (var key = Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam"))
                {
                    var sp = key?.GetValue("SteamPath") as string;
                    if (!string.IsNullOrEmpty(sp)) libs.Add(sp.Replace('/', '\\'));
                }
            }
            catch { }
            // parse libraryfolders.vdf of the main install for extra libraries
            var toScan = new List<string>(libs);
            foreach (var lib in libs.ToList())
            {
                try
                {
                    var vdf = Path.Combine(lib, "steamapps", "libraryfolders.vdf");
                    if (!File.Exists(vdf)) continue;
                    foreach (Match m in Regex.Matches(File.ReadAllText(vdf),
                                 "\"path\"\\s+\"([^\"]+)\""))
                        toScan.Add(m.Groups[1].Value.Replace("\\\\", "\\").Replace('/', '\\'));
                }
                catch { }
            }
            // common extra-library guesses on all drives
            foreach (var drive in DriveInfo.GetDrives())
            {
                if (drive.DriveType != DriveType.Fixed) continue;
                var guess = Path.Combine(drive.Name, "SteamLibrary");
                if (Directory.Exists(guess)) toScan.Add(guess);
            }
            foreach (var lib in toScan.Distinct(StringComparer.OrdinalIgnoreCase))
            {
                try
                {
                    var manifest = Path.Combine(lib, "steamapps", $"appmanifest_{AppId}.acf");
                    if (!File.Exists(manifest)) continue;
                    var mInst = Regex.Match(File.ReadAllText(manifest),
                        "\"installdir\"\\s+\"([^\"]+)\"");
                    if (!mInst.Success) continue;
                    var dir = Path.Combine(lib, "steamapps", "common", mInst.Groups[1].Value);
                    if (LooksLikeGameDir(dir) && !found.Contains(dir)) found.Add(dir);
                }
                catch { }
            }
            return found;
        }

        public static bool LooksLikeGameDir(string dir) =>
            !string.IsNullOrEmpty(dir) &&
            File.Exists(Path.Combine(dir, ExeName)) &&
            Directory.Exists(Path.Combine(dir, DataDir));

        // ---------------- hashing ----------------
        public static string Sha256File(string path)
        {
            using (var sha = SHA256.Create())
            using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 22))
                return BitConverter.ToString(sha.ComputeHash(fs)).Replace("-", "");
        }

        public enum FileState { Original, Patched, Unknown, Missing }

        public static FileState Classify(string path, string origSha, string newSha)
        {
            if (!File.Exists(path)) return FileState.Missing;
            var h = Sha256File(path);
            if (h == origSha) return FileState.Original;
            if (h == newSha) return FileState.Patched;
            return FileState.Unknown;
        }

        // ---------------- delta apply ----------------
        public static byte[] ApplyDelta(byte[] original, byte[] packedDelta)
        {
            byte[] ops;
            using (var ms = new MemoryStream(packedDelta))
            using (var ds = new DeflateStream(ms, CompressionMode.Decompress))
            using (var outMs = new MemoryStream())
            {
                ds.CopyTo(outMs);
                ops = outMs.ToArray();
            }
            int p = 0;
            byte[] magic = ReadBytes(ops, ref p, 4);
            if (magic[0] != (byte)'C' || magic[1] != (byte)'Z' || magic[2] != (byte)'P')
                throw new InvalidDataException("补丁数据格式错误");
            ulong newSize = ReadU64(ops, ref p);
            ulong opCount = ReadVarint(ops, ref p);
            var result = new byte[newSize];
            long w = 0;
            for (ulong i = 0; i < opCount; i++)
            {
                byte tag = ops[p++];
                if (tag == 0x01) // COPY origOffset, length
                {
                    ulong off = ReadVarint(ops, ref p);
                    ulong len = ReadVarint(ops, ref p);
                    Array.Copy(original, (long)off, result, w, (long)len);
                    w += (long)len;
                }
                else if (tag == 0x02) // INSERT literal
                {
                    ulong len = ReadVarint(ops, ref p);
                    Array.Copy(ops, p, result, w, (long)len);
                    p += (int)len;
                    w += (int)len;
                }
                else throw new InvalidDataException("补丁数据损坏（未知操作码）");
            }
            if (w != (long)newSize) throw new InvalidDataException("补丁数据长度校验失败");
            return result;
        }

        public static byte[] ReadResource(string name)
        {
            var asm = typeof(Program).Assembly;
            var res = asm.GetManifestResourceNames()
                .First(n => n.EndsWith(name, StringComparison.OrdinalIgnoreCase));
            using (var s = asm.GetManifestResourceStream(res))
            using (var ms = new MemoryStream())
            {
                s.CopyTo(ms);
                return ms.ToArray();
            }
        }

        private static byte[] ReadBytes(byte[] b, ref int p, int n)
        { var r = new byte[n]; Array.Copy(b, p, r, 0, n); p += n; return r; }
        private static ulong ReadU64(byte[] b, ref int p)
        { var v = BitConverter.ToUInt64(b, p); p += 8; return v; }
        private static ulong ReadVarint(byte[] b, ref int p)
        {
            ulong v = 0; int s = 0;
            while (true)
            {
                byte x = b[p++];
                v |= (ulong)(x & 0x7F) << s;
                if ((x & 0x80) == 0) return v;
                s += 7;
            }
        }

        // ---------------- core operations ----------------
        public static bool GameRunning =>
            Process.GetProcessesByName(Path.GetFileNameWithoutExtension(ExeName)).Length > 0;

        public static (FileState res, FileState dll) States(string gameDir)
        {
            var res = Classify(Path.Combine(gameDir, DataDir, ResName), ResOrig, ResNew);
            var dll = Classify(Path.Combine(gameDir, DataDir, "Managed", DllName), DllOrig, DllNew);
            return (res, dll);
        }

        public static void Install(string gameDir, Action<string> log)
        {
            string resPath = Path.Combine(gameDir, DataDir, ResName);
            string dllPath = Path.Combine(gameDir, DataDir, "Managed", DllName);
            var (rs, ds) = States(gameDir);
            if (rs == FileState.Patched && ds == FileState.Patched)
                throw new InvalidOperationException("游戏已经是汉化状态，无需重复安装。如需重装请先恢复原版。");
            if (rs != FileState.Original || ds != FileState.Original)
                throw new InvalidOperationException(ExplainBadState(rs, ds));

            Backup(resPath, log);
            Backup(dllPath, log);

            log("正在应用 resources.assets 差分补丁（约 13MB，请稍候）…");
            var newRes = ApplyDelta(File.ReadAllBytes(resPath), ReadResource("delta_res.bin"));
            Verify(newRes, ResNew, "resources.assets");
            WriteFile(resPath, newRes);
            log("resources.assets ✔");

            log("正在应用 Assembly-CSharp.dll 差分补丁…");
            var newDll = ApplyDelta(File.ReadAllBytes(dllPath), ReadResource("delta_dll.bin"));
            Verify(newDll, DllNew, "Assembly-CSharp.dll");
            WriteFile(dllPath, newDll);
            log("Assembly-CSharp.dll ✔");
        }

        public static void Restore(string gameDir, Action<string> log)
        {
            string resPath = Path.Combine(gameDir, DataDir, ResName);
            string dllPath = Path.Combine(gameDir, DataDir, "Managed", DllName);
            string resBak = resPath + BackupSuffix;
            string dllBak = dllPath + BackupSuffix;
            if (!File.Exists(resBak) && !File.Exists(dllBak))
                throw new InvalidOperationException("未找到备份文件（可能从未安装过本补丁，或备份被删除）。也可通过 Steam「校验文件完整性」恢复原版。");
            if (File.Exists(resBak))
            {
                File.Copy(resBak, resPath, true);
                log("resources.assets 已恢复 ✔");
            }
            if (File.Exists(dllBak))
            {
                File.Copy(dllBak, dllPath, true);
                log("Assembly-CSharp.dll 已恢复 ✔");
            }
            var (rs, ds) = States(gameDir);
            if (rs != FileState.Original || ds != FileState.Original)
                throw new InvalidOperationException("恢复后校验失败，请用 Steam「校验文件完整性」修复。");
        }

        private static void Backup(string path, Action<string> log)
        {
            var bak = path + BackupSuffix;
            if (File.Exists(bak)) return;
            File.Copy(path, bak);
            log($"已备份: {Path.GetFileName(path)}{BackupSuffix}");
        }

        private static void Verify(byte[] data, string expectSha, string what)
        {
            using (var sha = SHA256.Create())
            {
                var h = BitConverter.ToString(sha.ComputeHash(data)).Replace("-", "");
                if (h != expectSha)
                    throw new InvalidDataException($"{what} 补丁结果校验失败（内部错误）");
            }
        }

        private static void WriteFile(string path, byte[] data)
        {
            File.SetAttributes(path, FileAttributes.Normal);
            File.WriteAllBytes(path, data);
        }

        public static string ExplainBadState(FileState rs, FileState ds) =>
            (rs, ds) switch
            {
                (FileState.Unknown, _) or (_, FileState.Unknown) =>
                    "游戏文件与预期不一致：可能游戏版本不同或文件被修改过。\n请先在 Steam 中对本游戏执行「校验文件完整性」，再运行本补丁。",
                (FileState.Missing, _) or (_, FileState.Missing) =>
                    "找不到游戏文件，安装目录可能不完整。请通过 Steam 校验文件完整性。",
                _ => "当前文件状态不支持此操作。"
            };

        // ---------------- CLI mode (automation/testing) ----------------
        private static int RunCli(string dir, bool install, bool restore, bool stateOnly, string logPath)
        {
            var sb = new StringBuilder();
            int code = 0;
            try
            {
                dir = dir ?? FindGameDirs().FirstOrDefault();
                sb.AppendLine($"gameDir: {dir}");
                if (string.IsNullOrEmpty(dir) || !LooksLikeGameDir(dir)) { code = 2; sb.AppendLine("ERROR: game dir not found"); goto done; }
                if (GameRunning) { code = 5; sb.AppendLine("ERROR: game is running"); goto done; }
                var (rs, ds) = States(dir);
                sb.AppendLine($"res={rs} dll={ds}");
                if (stateOnly) goto done;
                if (install) { Install(dir, s => sb.AppendLine(s)); sb.AppendLine("INSTALL OK"); }
                if (restore) { Restore(dir, s => sb.AppendLine(s)); sb.AppendLine("RESTORE OK"); }
            }
            catch (Exception ex)
            {
                code = 1; sb.AppendLine("ERROR: " + ex.Message);
            }
        done:
            sb.AppendLine($"exit={code}");
            var text = sb.ToString();
            Console.Error.WriteLine(text);
            if (logPath != null) File.WriteAllText(logPath, text, Encoding.UTF8);
            return code;
        }
    }

    // ---------------- UI ----------------
    internal class MainForm : Form
    {
        private readonly TextBox _dirBox = new TextBox();
        private readonly Button _browseBtn = new Button();
        private readonly Button _findBtn = new Button();
        private readonly Label _stateLabel = new Label();
        private readonly Button _installBtn = new Button();
        private readonly Button _restoreBtn = new Button();
        private readonly TextBox _log = new TextBox();
        private readonly Label _footer = new Label();

        public MainForm(string dir)
        {
            Text = "ChuSinGura46+1 简体中文汉化补丁 v1.0";
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new System.Drawing.Size(680, 452);
            Font = new System.Drawing.Font("Microsoft YaHei UI", 9F);

            var intro = new Label
            {
                Text = "适用于 Steam 版《ChuSinGura46+1 S》(AppID 464780，当前构建 1370333)。\r\n" +
                       "补丁只包含差异数据；安装前会自动备份原版文件，可随时一键恢复。\r\n" +
                       "进入游戏后在设置中把语言循环切换到「简体中文」即可。",
                Dock = DockStyle.Top, Height = 58, Padding = new Padding(10, 8, 0, 0)
            };

            var dirPanel = new FlowLayoutPanel
            {
                Dock = DockStyle.Top, Height = 36, Padding = new Padding(8, 4, 0, 0),
                Controls = { new Label { Text = "游戏目录:", AutoSize = true, Padding = new Padding(0, 7, 0, 0) }, _dirBox, _browseBtn, _findBtn }
            };
            _dirBox.Width = 400;
            _browseBtn.Text = "浏览…";
            _browseBtn.AutoSize = true;
            _browseBtn.Click += (s, e) =>
            {
                using (var d = new FolderBrowserDialog { Description = "选择 ChuSinGura46+1 游戏根目录" })
                    if (d.ShowDialog(this) == DialogResult.OK) _dirBox.Text = d.SelectedPath;
                RefreshState();
            };
            _findBtn.Text = "自动查找";
            _findBtn.AutoSize = true;
            _findBtn.Click += (s, e) =>
            {
                var found = Program.FindGameDirs();
                if (found.Count == 0) MessageBox.Show(this, "没有找到已安装的游戏，请手动选择目录。", "提示");
                else _dirBox.Text = found[0];
                RefreshState();
            };

            _stateLabel.Dock = DockStyle.Top;
            _stateLabel.Height = 30;
            _stateLabel.Padding = new Padding(10, 8, 0, 0);

            var btnPanel = new FlowLayoutPanel
            {
                Dock = DockStyle.Top, Height = 48, Padding = new Padding(8, 6, 0, 0),
                Controls = { _installBtn, _restoreBtn }
            };
            _installBtn.Text = "安装汉化";
            _installBtn.AutoSize = true;
            _installBtn.Padding = new Padding(14, 4, 14, 4);
            _installBtn.Click += (s, e) => Run(true);
            _restoreBtn.Text = "恢复原版";
            _restoreBtn.AutoSize = true;
            _restoreBtn.Padding = new Padding(14, 4, 14, 4);
            _restoreBtn.Click += (s, e) => Run(false);

            _log.Dock = DockStyle.Fill;
            _log.Multiline = true;
            _log.ScrollBars = ScrollBars.Vertical;
            _log.ReadOnly = true;

            _footer.Dock = DockStyle.Bottom;
            _footer.Height = 24;
            _footer.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            _footer.ForeColor = System.Drawing.SystemColors.GrayText;
            _footer.Font = new System.Drawing.Font("Microsoft YaHei UI", 8F);
            _footer.Text = "补丁程序与构建工具 Copyright © 2026 Jin Lujia · 游戏本体版权归 Inre 所有，仅供正版用户学习交流";

            Controls.Add(_log);
            Controls.Add(btnPanel);
            Controls.Add(_stateLabel);
            Controls.Add(dirPanel);
            Controls.Add(intro);
            Controls.Add(_footer);

            _dirBox.TextChanged += (s, e) => RefreshState();

            var initial = dir ?? Program.FindGameDirs().FirstOrDefault() ?? "";
            _dirBox.Text = initial;
        }

        private void RefreshState()
        {
            string dir = _dirBox.Text.Trim();
            if (!Program.LooksLikeGameDir(dir))
            {
                _stateLabel.Text = "状态：目录无效（应包含 ChuSinGura46+1.exe 和 ChuSinGura46+1_Data）";
                _installBtn.Enabled = _restoreBtn.Enabled = false;
                return;
            }
            var (rs, ds) = Program.States(dir);
            _stateLabel.Text = $"状态：resources.assets = {Zh(rs)}；Assembly-CSharp.dll = {Zh(ds)}";
            _installBtn.Enabled = rs == Program.FileState.Original && ds == Program.FileState.Original;
            _restoreBtn.Enabled = rs == Program.FileState.Patched || ds == Program.FileState.Patched
                || File.Exists(Path.Combine(dir, Program.DataDir, "resources.assets.zh-backup"));
        }

        private static string Zh(Program.FileState s) => s switch
        {
            Program.FileState.Original => "原版",
            Program.FileState.Patched => "已汉化",
            Program.FileState.Missing => "缺失",
            _ => "无法识别"
        };

        private void Run(bool install)
        {
            string dir = _dirBox.Text.Trim();
            if (!Program.LooksLikeGameDir(dir)) return;
            if (Program.GameRunning)
            {
                MessageBox.Show(this, "游戏正在运行，请先退出游戏再操作。", "提示");
                return;
            }
            if (!CanWrite(dir) && !RelaunchElevated(dir))
                return; // elevated relaunch already happened, or user declined

            _installBtn.Enabled = _restoreBtn.Enabled = false;
            Log(install ? "===== 开始安装 =====" : "===== 开始恢复 =====");
            var t = new Thread(() =>
            {
                try
                {
                    if (install) Program.Install(dir, Log);
                    else Program.Restore(dir, Log);
                    Log(install ? "安装完成！从 Steam 启动游戏，在设置中切换语言为「简体中文」。"
                                : "已恢复为原版文件。");
                    Invoke(new Action(() => MessageBox.Show(this,
                        install ? "汉化安装成功！\n\n进入游戏后：右键打开设置（或点设置按钮），\n把语言循环切换到「简体中文」即可。" : "已恢复原版。",
                        "完成", MessageBoxButtons.OK, MessageBoxIcon.Information)));
                }
                catch (Exception ex)
                {
                    Log("错误: " + ex.Message);
                    Invoke(new Action(() => MessageBox.Show(this, ex.Message, "出错了", MessageBoxButtons.OK, MessageBoxIcon.Error)));
                }
                finally
                {
                    Invoke(new Action(RefreshState));
                }
            });
            t.IsBackground = true;
            t.Start();
        }

        private static bool CanWrite(string gameDir)
        {
            try
            {
                var probe = Path.Combine(gameDir, Program.DataDir, ".zhwrite_probe");
                File.WriteAllText(probe, "x");
                File.Delete(probe);
                return true;
            }
            catch (UnauthorizedAccessException) { return false; }
            catch { return true; } // other errors: let the real operation surface them
        }

        private bool RelaunchElevated(string dir)
        {
            if (MessageBox.Show(this,
                    "对游戏目录没有写入权限（通常游戏装在 Program Files）。\n需要以管理员身份重新运行补丁程序，是否继续？",
                    "需要管理员权限", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
                return false;
            try
            {
                var exe = Process.GetCurrentProcess().MainModule.FileName;
                Process.Start(new ProcessStartInfo(exe, "--dir \"" + dir + "\"") { Verb = "runas" });
                Close();
                return true;
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, "提权失败: " + ex.Message, "错误");
                return false;
            }
        }

        private void Log(string s) => Invoke(new Action(() =>
        {
            _log.AppendText(s + Environment.NewLine);
        }));
    }
}
