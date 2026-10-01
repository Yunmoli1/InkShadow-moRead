package android.content.res;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
public class AssetManager {
    private final Path root;
    public AssetManager(Path root) { this.root = root; }
    public InputStream open(String name) throws IOException {
        Path p = root.resolve(name).normalize();
        if (!p.startsWith(root) || !Files.isRegularFile(p)) throw new IOException("not found: " + name);
        return Files.newInputStream(p);
    }
}
