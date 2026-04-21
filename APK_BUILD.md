# 生成 APK（Kivy + Buildozer）

当前目录已准备好：
- `main.py`：安卓版组播广播 APP
- `buildozer.spec`：打包配置
- `.github/workflows/android-apk.yml`：GitHub Actions 自动打包 APK

## 1. 在 Linux/WSL 中安装依赖

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git zip unzip openjdk-17-jdk
pip install --upgrade pip
pip install buildozer cython
```

## 2. 进入项目目录后打包

```bash
buildozer android debug
```

首次构建时间较长（会下载 Android SDK/NDK）。

## 3. APK 输出位置

构建完成后，APK 在：

```bash
bin/*.apk
```

常见示例文件名：
- `bin/multicastbroadcast-0.1-arm64-v8a_armeabi-v7a-debug.apk`

## 4. 说明

- 这个 APP 使用 UDP 组播，适合局域网广播。
- 安卓真机测试时，需与其他设备在同一局域网。
- 部分路由器会限制组播转发，若收不到消息可先在同一 Wi-Fi 下多机测试。

## 5. GitHub Actions 自动打包（方案 B）

已配置工作流：`.github/workflows/android-apk.yml`

- 推送到 `main`/`master` 会自动构建
- 或在 GitHub Actions 页面手动点击 `Build Android APK` 的 `Run workflow`
- 构建完成后在该次运行页面的 `Artifacts` 下载 APK
