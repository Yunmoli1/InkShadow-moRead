package com.moread.app;

import android.content.Context;
import android.net.Uri;
import android.webkit.MimeTypeMap;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.Executors;

/**
 * 应用内置反向代理：
 *  - 非 /api 路径：从 assets/www 提供前端静态文件（无扩展名路径回退 index.html，支持 SPA 路由）
 *  - /api 路径：转发到 PC 端墨读服务器（默认 http://127.0.0.1:8686，可在应用内配置）
 *
 * 使用原始 ServerSocket 而非 WebViewClient 拦截，因为后者拿不到 POST 请求体。
 * 所有响应 Connection: close，按块流式写出（保证 SSE 与媒体 Range 播放）。
 */
public class ProxyServer {

    public interface BackendUrlProvider { String get(); }

    private final Context context;
    private final BackendUrlProvider backendUrl;
    private volatile ServerSocket serverSocket;
    public int port = 0;

    public ProxyServer(Context context, BackendUrlProvider backendUrl) {
        this.context = context;
        this.backendUrl = backendUrl;
    }

    public void start() throws IOException {
        serverSocket = new ServerSocket(0, 64, java.net.InetAddress.getLoopbackAddress());
        port = serverSocket.getLocalPort();
        Executors.newCachedThreadPool().execute(this::acceptLoop);
    }

    public void stop() {
        try {
            if (serverSocket != null) serverSocket.close();
        } catch (IOException ignored) { }
    }

    private void acceptLoop() {
        while (true) {
            try {
                Socket client = serverSocket.accept();
                Executors.newCachedThreadPool().execute(() -> handle(client));
            } catch (IOException e) {
                return; // server closed
            }
        }
    }

    private void handle(Socket client) {
        try {
            client.setTcpNoDelay(true);
            InputStream in = client.getInputStream();
            OutputStream out = client.getOutputStream();
            Request req = Request.parse(in);
            if (req == null) { client.close(); return; }

            if (req.rawPathAndQuery.startsWith("/api")) {
                proxy(req, in, out);
            } else {
                serveAsset(req, out);
            }
            out.flush();
            client.close();
        } catch (Exception e) {
            try { client.close(); } catch (IOException ignored) { }
        }
    }

    // ---- /api 反向代理 -------------------------------------------------------

    private void proxy(Request req, InputStream clientIn, OutputStream out) throws IOException {
        String base = backendUrl.get();
        if (base == null || base.isEmpty()) base = "http://127.0.0.1:8686";
        HttpURLConnection conn = null;
        try {
            URL url = new URL(base + req.rawPathAndQuery);
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod(req.method);
            conn.setConnectTimeout(4000);
            conn.setReadTimeout(0); // SSE / 大文件不限
            conn.setInstanceFollowRedirects(false);
            for (Map.Entry<String, String> h : req.headers.entrySet()) {
                String k = h.getKey();
                if (k.equalsIgnoreCase("host") || k.equalsIgnoreCase("connection")
                        || k.equalsIgnoreCase("accept-encoding") || k.equalsIgnoreCase("content-length")
                        || k.equalsIgnoreCase("origin") || k.equalsIgnoreCase("referer")) {
                    continue;
                }
                conn.setRequestProperty(k, h.getValue());
            }
            if (req.body != null && req.body.length > 0) {
                conn.setDoOutput(true);
                conn.setFixedLengthStreamingMode(req.body.length);
                OutputStream bo = conn.getOutputStream();
                bo.write(req.body);
                bo.flush();
            }
            int status = conn.getResponseCode();
            InputStream remote = status >= 400 ? conn.getErrorStream() : conn.getInputStream();
            if (remote == null) remote = conn.getInputStream();

            StringBuilder head = new StringBuilder();
            head.append("HTTP/1.1 ").append(status).append(' ')
                .append(conn.getResponseMessage() == null ? "" : conn.getResponseMessage())
                .append("\r\n");
            Map<String, java.util.List<String>> rh = conn.getHeaderFields();
            for (Map.Entry<String, java.util.List<String>> e : rh.entrySet()) {
                String k = e.getKey();
                if (k == null || k.equalsIgnoreCase("Transfer-Encoding")
                        || k.equalsIgnoreCase("Connection") || k.equalsIgnoreCase("Content-Length")) {
                    continue;
                }
                for (String v : e.getValue()) {
                    head.append(k).append(": ").append(v).append("\r\n");
                }
            }
            head.append("Connection: close\r\n\r\n");
            out.write(head.toString().getBytes(StandardCharsets.UTF_8));
            if (!"HEAD".equals(req.method) && remote != null) {
                byte[] buf = new byte[8192];
                int n;
                while ((n = remote.read(buf)) != -1) {
                    out.write(buf, 0, n);
                    out.flush();
                }
            }
        } catch (IOException e) {
            String msg = "{\"detail\":\"无法连接墨读服务器（" + base + "）。"
                    + "请在电脑上启动墨读并允许局域网访问（MOREAD_HOST=0.0.0.0），"
                    + "然后在 App 首页右下角设置服务器地址。\"}";
            byte[] body = msg.getBytes(StandardCharsets.UTF_8);
            String head = "HTTP/1.1 502 Bad Gateway\r\nContent-Type: application/json; charset=utf-8\r\n"
                    + "Content-Length: " + body.length + "\r\nConnection: close\r\n\r\n";
            out.write(head.getBytes(StandardCharsets.UTF_8));
            out.write(body);
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    // ---- 静态资源 ------------------------------------------------------------

    private void serveAsset(Request req, OutputStream out) throws IOException {
        String decoded = Uri.parse("http://local" + req.rawPathAndQuery).getPath();
        if (decoded == null || decoded.isEmpty()) decoded = "/";
        String rel = decoded.equals("/") ? "index.html" : decoded.substring(1);
        byte[] body = readAsset(rel);
        if (body == null && !rel.contains(".")) {
            body = readAsset("index.html"); // SPA 路由回退
            rel = "index.html";
        }
        if (body == null) {
            byte[] nf = "404 Not Found".getBytes(StandardCharsets.UTF_8);
            out.write(("HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nContent-Length: "
                    + nf.length + "\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.UTF_8));
            out.write(nf);
            return;
        }
        String mime = guessMime(rel);
        String head = "HTTP/1.1 200 OK\r\nContent-Type: " + mime
                + "\r\nContent-Length: " + body.length
                + "\r\nCache-Control: no-cache\r\nConnection: close\r\n\r\n";
        out.write(head.getBytes(StandardCharsets.UTF_8));
        if (!"HEAD".equals(req.method)) out.write(body);
    }

    private byte[] readAsset(String rel) {
        try (InputStream is = context.getAssets().open("www/" + rel)) {
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = is.read(buf)) != -1) bo.write(buf, 0, n);
            return bo.toByteArray();
        } catch (IOException e) {
            return null;
        }
    }

    private static String guessMime(String name) {
        String ext = MimeTypeMap.getFileExtensionFromUrl(name.toLowerCase());
        String m = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
        if (m != null) return m;
        Map<String, String> extra = new HashMap<>();
        extra.put("js", "application/javascript");
        extra.put("mjs", "application/javascript");
        extra.put("css", "text/css");
        extra.put("html", "text/html");
        extra.put("svg", "image/svg+xml");
        extra.put("webmanifest", "application/manifest+json");
        extra.put("json", "application/json");
        extra.put("woff2", "font/woff2");
        String e = ext == null ? "" : ext;
        return extra.getOrDefault(e, "application/octet-stream");
    }

    // ---- 请求解析 ------------------------------------------------------------

    static class Request {
        String method;
        String rawPathAndQuery; // 未解码，原样转发
        Map<String, String> headers = new LinkedHashMap<>();
        byte[] body;

        static Request parse(InputStream in) throws IOException {
            String line = readLine(in);
            if (line == null || line.isEmpty()) return null;
            String[] parts = line.split(" ");
            if (parts.length < 2) return null;
            Request r = new Request();
            r.method = parts[0];
            r.rawPathAndQuery = parts[1];
            int contentLength = 0;
            String l;
            while ((l = readLine(in)) != null && !l.isEmpty()) {
                int c = l.indexOf(':');
                if (c <= 0) continue;
                String k = l.substring(0, c).trim();
                String v = l.substring(c + 1).trim();
                r.headers.put(k, v);
                if (k.equalsIgnoreCase("content-length")) contentLength = Integer.parseInt(v);
            }
            if (contentLength > 0) {
                r.body = new byte[contentLength];
                int off = 0;
                while (off < contentLength) {
                    int n = in.read(r.body, off, contentLength - off);
                    if (n == -1) break;
                    off += n;
                }
            }
            return r;
        }

        private static String readLine(InputStream in) throws IOException {
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            int prev = -1, c;
            while ((c = in.read()) != -1) {
                if (prev == '\r' && c == '\n') break;
                if (prev != -1) bo.write(prev);
                prev = c;
            }
            return prev == '\r' ? new String(bo.toByteArray(), StandardCharsets.ISO_8859_1) : null;
        }
    }
}
