package android.content;
import android.content.res.AssetManager;
import java.nio.file.Path;
public class Context {
    private final AssetManager assets;
    public Context(Path assetRoot) { this.assets = new AssetManager(assetRoot); }
    public AssetManager getAssets() { return assets; }
}
