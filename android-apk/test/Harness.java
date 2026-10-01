import android.content.Context;
import com.moread.app.ProxyServer;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;

/** 桌面 JVM 冒烟测试：真实 ProxyServer 代码 + 假资源目录，对真实后端跑请求流。 */
public class Harness {
    public static void main(String[] args) throws Exception {
        Path assetsRoot = Paths.get(args[0]);
        Context ctx = new Context(assetsRoot);
        ProxyServer proxy = new ProxyServer(ctx, () -> "http://127.0.0.1:8686");
        proxy.start();
        int port = proxy.port;
        int fails = 0;

        // 1. 首页资产
        String index = bodyOf(httpGet(port, "/"));
        fails += check("index.html served", index.startsWith("<!doctype html>"));
        fails += check("no registerSW", !index.contains("registerSW"));

        // 2. SPA 路由回退
        String spa = bodyOf(httpGet(port, "/novels"));
        fails += check("SPA fallback", spa.startsWith("<!doctype html>"));

        // 3. /api/health 透传
        String health = bodyOf(httpGet(port, "/api/health"));
        fails += check("health passthrough", health.contains("\"status\":\"ok\""));

        // 4. PUT /api/settings（带请求体）
        String body = "{\"theme\":\"dark\",\"reader_font_size\":21}";
        String put = bodyOf(raw(port, "PUT", "/api/settings", body));
        fails += check("PUT settings (body forwarded)", put.contains("\"theme\":\"dark\""));

        // 5. 资产 MIME
        String cssHead = httpGet(port, "/assets/index-BCvpFzdG.css");
        fails += check("css mime", cssHead.contains("text/css"));

        // 6. 媒体 Range 透传（通过代理拿第一个媒体文件前 1KB）
        String media = bodyOf(httpGet(port, "/api/media?media_type=video&page_size=1"));
        String mid = extract(media, "\"id\":\"", "\"");
        if (mid != null) {
            String ranged = httpGetWithRange(port, "/api/media/" + mid + "/file");
            fails += check("media range passthrough", ranged.contains("HTTP/1.1 206"));
        } else {
            fails += check("media range passthrough (no video in library)", true);
        }

        System.out.println(fails == 0 ? "ALL PASS" : fails + " FAILURES");
        proxy.stop();
        System.exit(fails == 0 ? 0 : 1);
    }

    static String bodyOf(String resp) {
        int i = resp.indexOf("\r\n\r\n");
        return i >= 0 ? resp.substring(i + 4) : resp;
    }

    static String extract(String s, String start, String end) {
        int i = s.indexOf(start);
        if (i < 0) return null;
        int j = s.indexOf(end, i + start.length());
        return j < 0 ? null : s.substring(i + start.length(), j);
    }

    static int check(String name, boolean ok) {
        System.out.println((ok ? "PASS " : "FAIL ") + name);
        return ok ? 0 : 1;
    }

    static String httpGet(int port, String path) throws Exception {
        return raw(port, "GET", path, null);
    }

    static String httpGetWithRange(int port, String path) throws Exception {
        Socket s = new Socket("127.0.0.1", port);
        OutputStream out = s.getOutputStream();
        out.write(("GET " + path + " HTTP/1.1\r\nHost: t\r\nRange: bytes=0-1023\r\nConnection: close\r\n\r\n")
                .getBytes(StandardCharsets.ISO_8859_1));
        out.flush();
        InputStream in = s.getInputStream();
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) != -1) bo.write(buf, 0, n);
        s.close();
        return new String(bo.toByteArray(), StandardCharsets.ISO_8859_1);
    }

    static String raw(int port, String method, String path, String body) throws Exception {
        Socket s = new Socket("127.0.0.1", port);
        OutputStream out = s.getOutputStream();
        byte[] b = body == null ? new byte[0] : body.getBytes(StandardCharsets.UTF_8);
        String req = method + " " + path + " HTTP/1.1\r\nHost: t\r\nContent-Type: application/json\r\nContent-Length: " + b.length
                + "\r\nConnection: close\r\n\r\n";
        out.write(req.getBytes(StandardCharsets.ISO_8859_1));
        out.write(b);
        out.flush();
        InputStream in = s.getInputStream();
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) != -1) bo.write(buf, 0, n);
        s.close();
        return new String(bo.toByteArray(), StandardCharsets.UTF_8);
    }
}
