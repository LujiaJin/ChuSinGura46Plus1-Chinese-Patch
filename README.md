# ChuSinGura46+1 S 简体中文汉化补丁

![cover](docs/cover.jpg)

《ChuSinGura46+1 S -忠臣蔵46+1-》（Steam 版，AppID `464780`）的简体中文汉化补丁。
剧情文本、人物名、选项与系统文本全量汉化，共 **138,029** 条译文；日文、英文原文保留，
游戏内可随时在 简体中文 / English / 日本語 之间切换。

## 下载

到 [**Releases**](../../releases) 页面下载 `ChuSinGura46Plus1_ZH_Patch_v1.0.zip`（约 13.5 MB），解压后双击 `ChuSinGura46Plus1_ZH_Patch.exe` 即可。

- Windows 10 / 11 免安装任何运行库（.NET Framework 4.8 系统自带）
- 程序会自动定位 Steam 游戏目录，自动备份原版文件，支持一键恢复

## 安装步骤

1. 确保《ChuSinGura46+1 S》已通过 Steam 安装（且至少启动过一次）
2. **退出游戏**，双击 `ChuSinGura46Plus1_ZH_Patch.exe`
3. 确认界面中两个文件状态均显示「原版」，点击 **安装汉化**
   - 游戏装在 `Program Files` 时会请求一次管理员权限（UAC 弹窗），属正常现象
4. 从 Steam 启动游戏，在游戏中 **右键**（或点设置按钮）打开环境设置，
   将语言循环切换到 **「简体中文」**

## 功能与特性

| 特性 | 说明 |
| --- | --- |
| 双击安装 | 自动查找 Steam 库中的游戏（也支持手动选目录） |
| 完整校验 | 安装前校验原版文件 SHA256；安装后校验产物哈希，与实测版本逐字节一致 |
| 自动备份 | 原版文件备份为 `*.zh-backup`，点「恢复原版」即可一键还原 |
| 状态识别 | 自动识别 原版 / 已汉化 / 文件异常 三种状态并给出处理建议 |
| 版本保护 | 仅适配 Steam 构建 `1370333`；游戏将来若更新，安装器会拒绝安装并提示先做 Steam 文件校验 |
| 差分发布 | 补丁只含差异数据（约 13 MB），不包含游戏资源本体，必须配合正版游戏文件使用 |

## 常见问题

**Q：双击 exe 出现蓝色 SmartScreen 警告？**
程序未做代码签名，属于正常提示。点「更多信息」→「仍要运行」。

**Q：提示「游戏文件与预期不一致」？**
说明本地游戏文件与补丁适配的 Steam 构建不一致（版本不同或被修改过）。
在 Steam 库中右键该游戏 → 属性 → 已安装文件 → **验证游戏文件的完整性**，完成后重试。

**Q：想卸载汉化？**
补丁程序里点「恢复原版」，或直接做 Steam 文件完整性校验。存档不受影响。

**Q：中文模式下界面按钮图标是英文版的？**
中文模式沿用英文版 UI 底图，剧情、人物名、选项均为简体中文，不影响游玩。

## 技术原理

- 汉化文本写入游戏 `resources.assets` 内 121 个 TextAsset 的独立 `Zh` 列，
  并重编译 `Assembly-CSharp.dll` 增加第三语言档（English → 日本語 → 简体中文循环切换）；
- 发布包采用**差分**方式：`installer/data/delta_res.bin`（13.2 MB）与 `delta_dll.bin`
  记录 原版→汉化 的二进制差异，安装器在玩家本机文件上应用差分并做 SHA256 校验。
  目标产物：
  - `resources.assets` → `91361961…`
  - `Assembly-CSharp.dll` → `A9EB1755…`
  适配原版：
  - `resources.assets` → `9F0E61C9…`
  - `Assembly-CSharp.dll` → `5CCEAA7B…`
- `tools/` 内为差分生成脚本（需要 Python + [UnityPy](https://github.com/K0lb3/UnityPy)，
  以及本机合法拥有的原版与已汉化游戏文件，仓库中不提供）。
- 安装器源码在 `installer/`（C# / WinForms / .NET Framework 4.8）：

  ```
  dotnet build -c Release
  ```

## 声明

- 本补丁的安装器程序与构建工具 **Copyright © 2026 Jin Lujia**，汉化译文版权归汉化作者所有。
- 本补丁仅供学习交流，**需持有正版游戏**。游戏及全部素材版权归
  [Inre](https://store.steampowered.com/app/464780/) 所有。
- 请勿将本补丁用于商业用途或与游戏本体捆绑分发。
- 译文语料与游戏原始文本不在本仓库中公开分发。

## 反馈

遇到问题或想反馈译文，请到 [Issues](../../issues) 留言。
