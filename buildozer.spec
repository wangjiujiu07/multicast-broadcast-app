[app]
title = Multicast Broadcast
package.name = multicastbroadcast
package.domain = org.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 0.1
requirements = python3,kivy

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_MULTICAST_STATE,WAKE_LOCK
android.api = 33
android.minapi = 24
android.sdk = 33
android.ndk = 25b
android.build_tools_version = 34.0.0
android.accept_sdk_license = True
android.archs = arm64-v8a

log_level = 2
warn_on_root = 1

[buildozer]
log_level = 2
