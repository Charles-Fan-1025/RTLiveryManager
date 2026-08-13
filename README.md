# Running Train Livery Manager

一款用于 `Running Train` 的材质管理工具。

## 功能

- 涂装管理
  - 管理 `1100`、`1500`、`DC85`、`KR5000` 四种车型涂装
  - 查看游戏中 5 个涂装槽
  - 导入、导出、编辑、删除涂装
  - 将库中的涂装写入游戏槽位
- 涂装编辑
  - 将图片处理为游戏可用的涂装比例
  - 将处理后的图片还原为便于编辑的图片
- 设置
  - 配置游戏文件位置
  - 从游戏文件批量导入现有涂装

## 目录

- `FrontEnd.py`：GUI 入口
- `FileManage.py`：材质库与游戏文件管理后端
- `ImageProcess.py`：图片处理 / 还原后端
- `RTL_icon.png`、`RTL_icon.ico`：软件图标
- `GenerateIcon.py`：由 `RTL_icon.png` 生成 `.ico` 的临时脚本

## 依赖

- Python 3.10+
- Pillow

安装依赖：

```powershell
pip install pillow
```

## 运行

直接启动 GUI：

```powershell
python FrontEnd.py
```

图片处理模块也支持命令行：

```powershell
python ImageProcess.py -h
python ImageProcess.py -p -m 1100 -i "input.jpg" -o "output.jpg"
python ImageProcess.py -r -m 1100 -i "combined.jpg" -o "restored.jpg"
```

## 游戏路径

软件会把数据存放在用户文档目录：

```text
Documents/RunningTrainLivery/
```

其中包含：

- `Data/settings.json`
- `Data/liveries.json`
- `Livery/1100`
- `Livery/1500`
- `Livery/DC85`
- `Livery/KR5000`

首次启动时需要选择 `RUNNING TRAIN` 文件夹。

## 图标

项目自带 `RTL_icon.png` 和 `RTL_icon.ico`。

如果你重新生成图标，可运行：

```powershell
python GenerateIcon.py
```

如果后续打包为单文件 `.exe`，建议同时指定 exe 图标：

```powershell
pyinstaller --onefile --windowed --icon RTL_icon.ico FrontEnd.py
```

## 注意事项

- 软件启动时会提示免责声明和备份建议，可勾选“不再提醒”。
- `DC85` 涂装在游戏中会左右翻转，这是游戏限制。
- 导入涂装时，程序会过滤掉已知的空白/占位材质哈希。
- 图片导入时会自动标准化尺寸：
  - 涂装图：`2048x2048`
  - 缩略图：`1000x800`

## 许可

开源项目，按仓库实际许可为准。
