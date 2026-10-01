package android.webkit;
import java.util.HashMap;
import java.util.Map;
public class MimeTypeMap {
    private static final MimeTypeMap S = new MimeTypeMap();
    private static final Map<String, String> M = new HashMap<>();
    static {
        M.put("html", "text/html"); M.put("js", "application/javascript");
        M.put("css", "text/css"); M.put("png", "image/png");
        M.put("svg", "image/svg+xml"); M.put("json", "application/json");
        M.put("webmanifest", "application/manifest+json");
    }
    public static MimeTypeMap getSingleton() { return S; }
    public String getMimeTypeFromExtension(String e) { return M.get(e); }
    public static String getFileExtensionFromUrl(String n) {
        int d = n.lastIndexOf('.');
        return d >= 0 ? n.substring(d + 1) : "";
    }
}
