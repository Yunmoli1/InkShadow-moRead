#!/usr/bin/env bash
# 墨读 Android APK 构建脚本（Windows，Git Bash）
# 前置：JDK 17+、Android build-tools 34 + platform android-34（SDK_PATH 按需修改）
set -e
SDK_PATH="${SDK_PATH:-/d/Android/Sdk}"
BT="$SDK_PATH/build-tools/34.0.0"
PLAT="$SDK_PATH/platforms/android-34/android.jar"
cd "$(dirname "$0")/.."   # 项目根

echo "[1/6] 准备前端资产"
cd android-apk
rm -rf assets && mkdir -p assets/www
cp -r ../frontend/dist/* assets/www/
rm -f assets/www/registerSW.js assets/www/sw.js assets/www/workbox-*.js
python - <<'EOF'
import re
p = 'assets/www/index.html'
s = open(p, encoding='utf-8').read()
s = re.sub(r'<script id="vite-plugin-pwa:register-sw"[^>]*></script>', '', s)
open(p, 'w', encoding='utf-8').write(s)
EOF
[ -f res/mipmap/ic_launcher.png ] || cp assets/www/pwa-192.png res/mipmap/ic_launcher.png

echo "[2/6] aapt2 编译链接"
rm -rf build && mkdir -p build/gen build/classes build/dex
"$BT/aapt2.exe" compile --dir res -o build/res.zip
"$BT/aapt2.exe" link -o build/unsigned.apk -I "$PLAT" --manifest AndroidManifest.xml \
    -A assets build/res.zip --java build/gen \
    --min-sdk-version 24 --target-sdk-version 34 \
    --version-code 1 --version-name 1.0.0 --auto-add-overlay

echo "[3/6] javac + d8"
javac --release 17 -classpath "$PLAT" -d build/classes \
    java/com/moread/app/*.java build/gen/com/moread/app/R.java
"$BT/d8.bat" --release --lib "$PLAT" --output build/dex $(find build/classes -name "*.class")

echo "[4/6] 组装 + 对齐"
python - <<'EOF'
import zipfile, shutil
shutil.copy('build/unsigned.apk', 'build/with-dex.apk')
with zipfile.ZipFile('build/with-dex.apk', 'a', zipfile.ZIP_DEFLATED) as z:
    z.write('build/dex/classes.dex', 'classes.dex')
EOF
"$BT/zipalign.exe" -f 4 build/with-dex.apk build/aligned.apk

echo "[5/6] 签名"
[ -f keystore/debug.keystore ] || keytool -genkeypair -keystore keystore/debug.keystore \
    -alias moread -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass moread123 -keypass moread123 -dname "CN=MoRead Debug,O=MoRead,C=CN"
"$BT/apksigner.bat" sign --ks keystore/debug.keystore --ks-pass pass:moread123 \
    --key-pass pass:moread123 --out moread.apk build/aligned.apk

echo "[6/6] 交付"
"$BT/apksigner.bat" verify moread.apk
cp moread.apk ../releases/moread.apk
echo "完成: releases/moread.apk"
