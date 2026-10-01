package com.moread.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.Toast;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class MainActivity extends Activity {

    private static final String PREFS = "moread";
    private static final String KEY_SERVER = "server_url";
    private static final String DEFAULT_SERVER = "http://127.0.0.1:8686";

    private WebView webView;
    private ProxyServer proxy;
    private SharedPreferences prefs;
    private final Handler ui = new Handler(Looper.getMainLooper());

    private String serverUrl() {
        String s = prefs.getString(KEY_SERVER, DEFAULT_SERVER).trim();
        if (s.isEmpty()) s = DEFAULT_SERVER;
        if (!s.startsWith("http://") && !s.startsWith("https://")) s = "http://" + s;
        while (s.endsWith("/")) s = s.substring(0, s.length() - 1);
        return s;
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE);

        webView = new WebView(this);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.setBackgroundColor(Color.rgb(0xfd, 0xf6, 0xe3));
        webView.setWebViewClient(new WebViewClient()); // http://127.0.0.1 同源，无需拦截

        FrameLayout root = new FrameLayout(this);
        root.addView(webView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // 右下角半透明设置按钮：随时修改服务器地址
        Button gear = new Button(this);
        gear.setText("⚙");
        gear.setBackgroundColor(0x22000000);
        gear.setTextColor(0xFF444444);
        gear.setAllCaps(false);
        FrameLayout.LayoutParams gp = new FrameLayout.LayoutParams(
                dp(40), dp(40), Gravity.BOTTOM | Gravity.END);
        gp.setMargins(0, 0, dp(10), dp(24));
        gear.setOnClickListener(v -> promptServerUrl(false));
        root.addView(gear, gp);
        setContentView(root);

        proxy = new ProxyServer(this, this::serverUrl);
        try {
            proxy.start();
        } catch (Exception e) {
            Toast.makeText(this, "代理服务启动失败: " + e.getMessage(), Toast.LENGTH_LONG).show();
            finish();
            return;
        }
        webView.loadUrl("http://127.0.0.1:" + proxy.port + "/");

        checkHealth(ok -> { if (!ok) promptServerUrl(true); });
    }

    // ---- 服务器连通性检查与配置 ----------------------------------------------

    private interface HealthCallback { void onResult(boolean ok); }

    private void checkHealth(HealthCallback cb) {
        new Thread(() -> {
            boolean ok = false;
            try {
                HttpURLConnection conn = (HttpURLConnection)
                        new URL(serverUrl() + "/api/health").openConnection();
                conn.setConnectTimeout(3000);
                conn.setReadTimeout(4000);
                try (InputStream is = conn.getInputStream()) {
                    ok = is.read() != -1;
                }
            } catch (Exception ignored) { }
            boolean finalOk = ok;
            ui.post(() -> cb.onResult(finalOk));
        }).start();
    }

    private void promptServerUrl(boolean firstRun) {
        View box = getLayoutInflater().inflate(R.layout.server_dialog, null);
        EditText input = box.findViewById(R.id.server_input);
        input.setText(prefs.getString(KEY_SERVER, DEFAULT_SERVER));
        new AlertDialog.Builder(this)
                .setTitle(firstRun ? "连接墨读服务器" : "服务器设置")
                .setMessage(firstRun
                        ? "未检测到墨读服务器。\n\n1. 在电脑上运行墨读（moread.exe），"
                          + "并以 MOREAD_HOST=0.0.0.0 启动以允许局域网访问；\n"
                          + "2. 填写电脑的局域网地址，如 192.168.1.100:8686。\n\n"
                          + "同一局域网内的手机即可使用全部功能（书架/阅读/笔记/下载/媒体播放）。"
                        : "填写墨读服务器地址（电脑局域网 IP + 端口）：")
                .setView(box)
                .setPositiveButton("保存", (d, w) -> {
                    prefs.edit().putString(KEY_SERVER, input.getText().toString().trim()).apply();
                    Toast.makeText(this, "已保存，正在重连…", Toast.LENGTH_SHORT).show();
                    checkHealth(ok -> {
                        Toast.makeText(this, ok ? "已连接 ✓" : "仍无法连接，请检查地址与防火墙",
                                Toast.LENGTH_LONG).show();
                    });
                    webView.reload();
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        if (proxy != null) proxy.stop();
        if (webView != null) webView.destroy();
        super.onDestroy();
    }
}
