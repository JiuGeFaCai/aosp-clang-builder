# AOSP Clang Builder

在 GitHub Actions 原生 ARM64 / x86_64 Linux runner 上，按 AOSP 指定的 LLVM 基础提交和补丁集重编译 Clang。默认版本是 `r536225`，可在运行时自定义版本、提交、LLVM 后端和 CMake 参数。

产物包含 Clang、lld、常用 LLVM 内核工具、Clang 内置头文件、源码与构建记录，以及 SHA-256 校验文件。

## Ubuntu 22.04 编译，Ubuntu 24.04 能用吗？

**可以用于同一 CPU 架构的 Ubuntu 24.04。** 默认选择 `ubuntu-22.04-arm`，产物供 ARM64 Linux 主机运行；工作流会再用原生 `ubuntu:24.04` 容器执行 Clang、lld 和 AArch64 ThinLTO/KCFI 编译链接检查，通过后才上传工具链。

Ubuntu 22.04 使用 glibc 2.35，Ubuntu 24.04 使用 glibc 2.39。旧发行版构建的程序通常可在新发行版运行；反向使用可能遇到缺少 `GLIBC_x.y` 符号。因此，需要同时兼容 22.04 和 24.04 时，保留默认的 22.04 runner。实际最低 glibc 版本会写入 `BUILD_INFO.json`。

参考：[Ubuntu 22.04 libc6](https://packages.ubuntu.com/jammy/libc6)、[Ubuntu 24.04 libc6](https://packages.ubuntu.com/noble/libc6)、[GitHub runner 标签](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)。

ARM64 和 x86_64 指的是 **Clang 自身运行的主机架构**；`targets` 指 Clang 可生成代码的架构。手机中的 Ubuntu chroot/proot 属于 Linux 主机环境；原生 Termux 的 Bionic 环境需要单独的构建配置。

## 用 GitHub Actions 编译

1. 创建名为 `aosp-clang-builder` 的 GitHub 仓库。公开仓库可使用免费的标准 GitHub-hosted runner。
2. 将本项目内容上传到仓库的默认分支，包含隐藏目录 `.github`。`build.yml` 必须位于 `.github/workflows/build.yml`。
3. 打开 **Actions → Build AOSP Clang → Run workflow**。
4. 第一次保留默认参数，即编译 `r536225` 的 ARM64 Linux 主机版。
5. 成功后在运行页面的 **Artifacts** 下载工具链。解开 Artifact 的 ZIP 后，再解开里面的 `.tar.xz`。

工作流只需 GitHub 自动提供的 token，无需添加 Secrets。仓库不需要预先存放 LLVM 源码。

| 输入 | 默认值 | 用法 |
| --- | --- | --- |
| `clang_revision` | `r536225` | AOSP 编号，可写 `clang-r536225`；其他示例：`r547379`、`r522817` |
| `toolchain_ref` | 留空 | `llvm_android` 的提交 SHA 或分支；决定版本元数据和补丁集 |
| `llvm_ref` | 留空 | 上游 `llvm/llvm-project` 的提交 SHA 或 ref；默认使用 AOSP 声明的基础提交 |
| `runner` | `ubuntu-22.04-arm` | 可选 22.04 / 24.04 的 ARM64 或 x86_64 runner |
| `targets` | `AArch64;ARM;X86;BPF` | LLVM 后端；只编 ARM64 内核可用 `AArch64;ARM;BPF`，`Native` 表示主机后端 |
| `projects` | `clang;lld` | 可增加 `;clang-tools-extra`，同时构建 clang-tidy、clangd 等工具 |
| `jobs` | `0` | 自动按 CPU 和内存选编译并行数；链接固定为 1 个任务 |
| `cmake_args` | 留空 | 额外 `-DKEY=VALUE` 参数，例如 `-DLLVM_ENABLE_ASSERTIONS=ON` |

`cmake_args` 中带空格的值需要整体引号，例如 `-DCMAKE_CXX_FLAGS="-O2 -g0"`。参数通过 argv 传给 CMake，不经 shell eval。

## 如何准确选择一个 AOSP 版本

`r536225` 默认固定使用官方 `manifest_12833971.xml` 中的 `llvm_android` 提交：

```text
43ef7af1325b43e13d926d74a89741d4ace5fcf8
```

基础 LLVM 提交从该提交的 `android_version.py` 读取：

```text
fc57f88f007497a4ead0ec8607ac66e1847b02d6
```

其他不带后缀的版本会先查找 `llvm-r<编号>-release`，再查找 `llvm-r<编号>`，使用分支当前的版本。例如 `r522817` 分支当前元数据声明 `r522817d`，产物会准确记录并使用这个实际编号。工作流将分支解析成完整 SHA，并记录每个实际应用的补丁及其 SHA-256。对重复构建有要求时，将成功运行记录中的 `toolchain_commit` 和 `llvm_commit` 填回两个 ref 输入。

**同一个 r 编号也可能有不同补丁集。** 要重建某个官方包，在它的 `manifest_*.xml` 中查找 `toolchain/llvm_android` 项目，将其 `revision` 填入 `toolchain_ref`；基础 LLVM 提交和补丁级别仍由这份元数据读取。`r536225b` 等带后缀版本必须提供该包对应的 `toolchain_ref`，防止静默使用其他变体的补丁。

`llvm_ref` 是高级覆盖项：如果与 AOSP 声明的基础提交不同，产物记录会标明 `custom_llvm_base: true`，补丁可能无法应用。一般保留空白即可。

版本需要提供 `android_version.py` 和 `patches/PATCHES.json`；当前与旧版的两种脚本目录布局都可识别。补丁按 `PATCHES.json` 的顺序和版本区间应用，使用官方相同的 GNU patch 参数，任何补丁失败都会停止。构建使用 Release 配置，静态链接 libstdc++ 和 libgcc；性能优化配置与 Google 官方 PGO/BOLT/MLGO 制品可能不同。

版本依据：[官方 r536225 manifest 的镜像](https://github.com/msft-mirror-aosp/platform.prebuilts.clang.host.linux-x86/blob/android16-release/clang-r536225/manifest_12833971.xml)、[固定的 AOSP 版本元数据](https://github.com/aosp-mirror-neo/toolchain_llvm_android/blob/43ef7af1325b43e13d926d74a89741d4ace5fcf8/src/llvm_android/android_version.py)。

## 在 Ubuntu 24.04 ARM64 本机运行

需要 Python 3.12+、CMake 3.28+、Clang、lld、Ninja、Git、GNU patch/binutils 和 xz。

```bash
sudo apt-get update
sudo apt-get install -y build-essential clang lld cmake ninja-build git patch python3 binutils file xz-utils ca-certificates

python3 scripts/build.py all --clang-revision r536225
```

其他版本：

```bash
python3 scripts/build.py all \
  --clang-revision r547379 \
  --targets 'AArch64;ARM;BPF' \
  --work-dir .build-r547379 \
  --output-dir dist
```

重新选择版本时使用新的 `--work-dir`，以保留已准备好的源码并避免重复应用补丁。本地构建不会自动执行 Docker 兼容性检查；可以在 `verify` 之后、`package` 之前单独运行：

```bash
python3 scripts/build.py compatibility --work-dir .build
python3 scripts/build.py package --work-dir .build --output-dir dist
```

产物格式：

```text
clang-r536225-linux-aarch64.tar.xz
clang-r536225-linux-aarch64.tar.xz.sha256
BUILD_INFO.json
```

## 使用工具链

```bash
sha256sum -c clang-r536225-linux-aarch64.tar.xz.sha256
tar -xf clang-r536225-linux-aarch64.tar.xz
export PATH="$PWD/clang-r536225-linux-aarch64/bin:$PATH"
clang --version
file "$(command -v clang)"
```

对使用普通 Make 的内核，可指定 `LLVM=1` 和对应交叉编译目标。Android 6.12 GKI 默认使用 Kleaf/Bazel，接入时还需配置 ARM64 主机版本的 Bazel、工具链路径及其他构建工具。这个项目的成功校验范围是编译器与 LLVM 工具的架构、交叉编译、链接和 AArch64 ThinLTO/KCFI；完整 GKI 构建仍需使用实际内核源码验证。

如果编译失败，运行页面会保留日志 Artifact；正常运行的时间上限为 6 小时。LLVM 版本越新、后端与额外项目越多，构建的时间和磁盘需求越大。
