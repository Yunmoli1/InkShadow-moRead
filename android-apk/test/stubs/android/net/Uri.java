package android.net;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
public class Uri {
    private final String path;
    private Uri(String path) { this.path = path; }
    public static Uri parse(String s) {
        String p = s;
        int scheme = p.indexOf("://");
        if (scheme >= 0) p = p.substring(scheme + 3);
        int slash = p.indexOf('/');
        p = slash >= 0 ? p.substring(slash) : "/";
        int q = p.indexOf('?');
        if (q >= 0) p = p.substring(0, q);
        int h = p.indexOf('#');
        if (h >= 0) p = p.substring(0, h);
        String dec = URLDecoder.decode(p.replace("+", "%2B"), StandardCharsets.UTF_8);
        return new Uri(dec);
    }
    public String getPath() { return path; }
}
