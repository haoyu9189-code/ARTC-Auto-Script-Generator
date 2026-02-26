# 🚀 快速开始 - 补充说明

## 方式 1：源码运行（开发者推荐）⚡

### Windows 用户
```bash
# 1. 克隆项目
git clone https://github.com/haoyu9189-code/ARTC-Auto-Script-Generator.git
cd ARTC-Auto-Script-Generator

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行程序
python main.py
```

### Linux/Mac 用户
```bash
# 1. 克隆项目
git clone https://github.com/haoyu9189-code/ARTC-Auto-Script-Generator.git
cd ARTC-Auto-Script-Generator

# 2. 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行程序
python main.py
```

---

## 方式 2：下载打包版本 📦

**适合不想配置 Python 环境的用户**

1. 前往 [Releases](https://github.com/haoyu9189-code/ARTC-Auto-Script-Generator/releases) 页面
2. 下载最新版本的 `SmartAM_vX.X.X.exe` (Windows) 或对应平台版本
3. 双击运行即可

---

## 验证安装

```bash
# 验证所有依赖是否安装成功
python -c "import PyQt5, numpy, pandas, scipy, matplotlib, pyvista; print('✅ All dependencies OK!')"
```

如果遇到错误，请检查：
- Python 版本 >= 3.7
- pip 已更新到最新版本：`python -m pip install --upgrade pip`
- 系统是否安装了必要的图形库（Linux 需要 `libgl1-mesa-glx`）

---

## 配置 Abaqus 路径（可选）

如果需要直接在软件内执行仿真，编辑 `config.py`：

```python
ABAQUS_COMMAND = "abaqus"  # 改为你的 Abaqus 可执行文件路径
# 例如：Windows: "C:\\SIMULIA\\Abaqus\\Commands\\abaqus.bat"
#      Linux: "/opt/SIMULIA/Commands/abaqus"
```

---

## 打包成可执行文件（开发者）

```bash
# 安装 PyInstaller
pip install pyinstaller

# 使用提供的 spec 文件打包
pyinstaller SmartAM.spec

# 生成的可执行文件在 dist/ 目录下
```
