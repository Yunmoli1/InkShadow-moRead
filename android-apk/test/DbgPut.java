import android.content.Context;
import com.moread.app.ProxyServer;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Paths;

public class DbgPut {
    public static void main(String[] a) throws Exception {
        ProxyServer proxy = new ProxyServer(new Context(Paths.get(a[0])), () -> "http://127.0.0.1:8686");
        proxy.start();
        Socket s = new Socket("127.0.0.1", proxy.port);
        String body = "{\"theme\":\"dark\",\"reader_font_size\":21}";
        OutputStream out = s.getOutputStream();
        out.write(("PUT /api/settings HTTP/1.1\r\nHost: t\r\nContent-Type: application/json\r\nContent-Length: "
                + body.length() + "\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.ISO_8859_1));
        out.write(body.getBytes(StandardCharsets.UTF_8));
        out.flush();
        InputStream in = s.getInputStream();
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[4096]; int n;
        while ((n = in.read(buf)) != -1) bo.write(buf, 0, n);
        System.out.println(new String(bo.toByteArray(), StandardCharsets.UTF_8).substring(0, Math.min(400, bo.size())));
        proxy.stop();
    }
}
