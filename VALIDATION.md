验证记录：2026-10-11。

已通过的检查：

- actionlint 1.7.12：GitHub Actions 工作流语法与输入检查。
- 8 项 Python 测试：补丁版本边界与顺序、嵌套仓库中的补丁应用、固定默认提交、分支回退、版本变体识别及安全读取版本元数据。
- 对 LLVM 基础提交 `fc57f88f007497a4ead0ec8607ac66e1847b02d6` 中补丁涉及的原始文件，按固定的 AOSP `llvm_android` 提交 `43ef7af1325b43e13d926d74a89741d4ace5fcf8` 应用了全部 57 个补丁，均成功。使用了与官方一致的 GNU patch 参数。
- 实际解析了 `r522817` 和 `r547379` 的发布分支与版本元数据；前者解析到 `r522817d`，后者为 `r547379`。
- 核对了 Ubuntu 22.04 ARM64 的 Python 3.12 runner 包及 CMake ARM64 wheel。

本地验证范围为工作流、版本元数据、补丁链与 Python 测试。完整 CMake 配置、LLVM 编译和 Ubuntu 24.04 容器运行检查由 GitHub Actions 执行，结果以仓库中的 Actions 运行记录为准。

首次 CI 已成功编译 ARM64 Clang 19.0.1，并通过交叉编译及 ThinLTO/KCFI 检查，最低 glibc 为 2.35。干净的 Ubuntu 24.04 容器缺少 lld 自动引入的 libxml2.so.2；已在默认构建配置中关闭可选的 libxml2 依赖，修复后的构建结果见最新 Actions 运行。

上传项目并启动工作流后，将执行真实编译、所有安装工具的 ELF 架构与动态依赖检查、所选后端的交叉编译检查、AArch64 ThinLTO/KCFI 链接检查，以及 Ubuntu 24.04 容器检查。全部通过后才上传工具链压缩包。
