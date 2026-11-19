package ru.klinrek.drugscore;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.util.Base64;

import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;
import java.util.zip.GZIPInputStream;

/**
 * Offline drug snapshot installer. Only signed manifests are trusted.
 * The published manifest MUST be signed with the OTA P-256 private key
 * (SHA256withECDSA) and served with drugs.db.gz at BASE.
 * No automatic network access: caller must explicitly invoke install().
 */
public final class DrugsDatabase {
    private static final String BASE = "https://victorpolekslab.github.io/Spravochnik_nmp/drugs-package/";
    private static final String PUBKEY = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE5WvSOIL6cIW9vXE1j5GHCvbqFnsvOhZB6dmcjXbS4laIBJ+DahXlPWpBJNhZ3PqO1znJztWjBj6/H8jEsDXKTQ==";
    private static final long MAX_COMPRESSED = 250L * 1024 * 1024;
    private static final long MAX_UNCOMPRESSED = 1024L * 1024 * 1024;
    private static final int BUFFER = 64 * 1024;
    private DrugsDatabase() {}

    private static File active(Context context) {
        File target = context.getDatabasePath("drugs-offline.db");
        File backup = new File(target.getParentFile(), "drugs-previous.tmp");
        // Restore a valid previous database after interruption between rename operations.
        if (!target.exists() && backup.isFile()) backup.renameTo(target);
        return target;
    }

    private static byte[] readSmall(String url, int max) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(20000);
        try (InputStream in = c.getInputStream(); java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream()) {
            byte[] buf = new byte[4096];
            int n;
            while ((n = in.read(buf)) != -1) {
                if (out.size() + n > max) throw new IllegalStateException("Metadata too large");
                out.write(buf, 0, n);
            }
            return out.toByteArray();
        } finally { c.disconnect(); }
    }

    private static void verifySignature(byte[] manifest, byte[] signature) throws Exception {
        byte[] der = Base64.decode(PUBKEY, Base64.DEFAULT);
        PublicKey key = KeyFactory.getInstance("EC").generatePublic(new X509EncodedKeySpec(der));
        Signature verifier = Signature.getInstance("SHA256withECDSA");
        verifier.initVerify(key);
        verifier.update(manifest);
        if (!verifier.verify(signature)) throw new SecurityException("Invalid drugs manifest signature");
    }

    private static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte v : b) sb.append(String.format(java.util.Locale.US, "%02x", v & 255));
        return sb.toString();
    }

    public static String version(Context context) {
        File file = active(context);
        if (!file.isFile()) return "";
        try (SQLiteDatabase db = SQLiteDatabase.openDatabase(file.getPath(), null, SQLiteDatabase.OPEN_READONLY);
             Cursor c = db.rawQuery("SELECT value FROM meta WHERE key='version'", null)) {
            return c.moveToFirst() ? c.getString(0) : "";
        } catch (Exception e) { return ""; }
    }

    public static String instruction(Context context, String id) {
        if (id == null || !id.matches("[a-zA-Z0-9_-]{1,80}")) return null;
        File file = active(context);
        if (!file.isFile()) return null;
        try (SQLiteDatabase db = SQLiteDatabase.openDatabase(file.getPath(), null, SQLiteDatabase.OPEN_READONLY);
             Cursor c = db.rawQuery("SELECT json FROM docs WHERE id=?", new String[]{id})) {
            return c.moveToFirst() ? c.getString(0) : null;
        } catch (Exception e) { return null; }
    }

    public static String index(Context context, String key) {
        if (!"search".equals(key) && !"ix".equals(key)) return null;
        File file = active(context);
        if (!file.isFile()) return null;
        try (SQLiteDatabase db = SQLiteDatabase.openDatabase(file.getPath(), null, SQLiteDatabase.OPEN_READONLY);
             Cursor c = db.rawQuery("SELECT value FROM meta WHERE key=?", new String[]{key})) {
            return c.moveToFirst() ? c.getString(0) : null;
        } catch (Exception e) { return null; }
    }

    /**
     * Lightweight signed manifest check. Does not download or install the database.
     * Call from a worker thread; network failures must not invalidate the offline copy.
     */
    public static String availableVersion() throws Exception {
        byte[] manifest = readSmall(BASE + "drugs-manifest.json", 32768);
        byte[] signature = readSmall(BASE + "drugs-manifest.sig", 4096);
        verifySignature(manifest, Base64.decode(new String(signature, StandardCharsets.US_ASCII).trim(), Base64.DEFAULT));
        JSONObject m = new JSONObject(new String(manifest, StandardCharsets.UTF_8));
        if (m.getInt("schema") != 1 || !"sqlite3+gzip".equals(m.getString("format"))
                || !"drugs.db.gz".equals(m.getString("file"))
                || !m.getString("sha256").matches("[0-9a-f]{64}")
                || m.getLong("size") <= 0 || m.getLong("size") > MAX_COMPRESSED
                || m.getInt("documents") <= 0) throw new SecurityException("Invalid signed drug package manifest");
        String v = m.getString("version");
        if (v.length() == 0 || v.length() > 128) throw new SecurityException("Invalid drug package version");
        return v;
    }

    public static synchronized String install(Context context) throws Exception {
        byte[] manifestBytes = readSmall(BASE + "drugs-manifest.json", 32768);
        byte[] signature = readSmall(BASE + "drugs-manifest.sig", 4096);
        verifySignature(manifestBytes, Base64.decode(new String(signature, StandardCharsets.US_ASCII).trim(), Base64.DEFAULT));
        JSONObject m = new JSONObject(new String(manifestBytes, StandardCharsets.UTF_8));
        if (m.getInt("schema") != 1 || !"sqlite3+gzip".equals(m.getString("format"))
                || !"drugs.db.gz".equals(m.getString("file"))) throw new SecurityException("Unsupported package");
        long expected = m.getLong("size");
        if (expected <= 0 || expected > MAX_COMPRESSED) throw new SecurityException("Invalid package size");
        String expectedHash = m.getString("sha256");
        if (!expectedHash.matches("[0-9a-f]{64}")) throw new SecurityException("Invalid SHA-256");
        File target = active(context);
        File dir = target.getParentFile();
        if (!dir.exists() && !dir.mkdirs()) throw new IllegalStateException("Cannot create database directory");
        File archive = new File(dir, "drugs-download.tmp");
        File staging = new File(dir, "drugs-install.tmp");
        File previous = new File(dir, "drugs-previous.tmp");
        try {
            HttpURLConnection c = (HttpURLConnection) new URL(BASE + "drugs.db.gz").openConnection();
            c.setConnectTimeout(15000);
            c.setReadTimeout(60000);
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            long bytes = 0;
            try (InputStream in = c.getInputStream(); FileOutputStream out = new FileOutputStream(archive)) {
                byte[] buf = new byte[BUFFER];
                int n;
                while ((n = in.read(buf)) != -1) {
                    bytes += n;
                    if (bytes > expected) throw new SecurityException("Archive larger than manifest");
                    digest.update(buf, 0, n);
                    out.write(buf, 0, n);
                }
                out.getFD().sync();
            } finally { c.disconnect(); }
            if (bytes != expected || !expectedHash.equals(hex(digest.digest())))
                throw new SecurityException("Archive SHA-256 mismatch");
            long expanded = 0;
            try (GZIPInputStream in = new GZIPInputStream(new FileInputStream(archive));
                 FileOutputStream out = new FileOutputStream(staging)) {
                byte[] buf = new byte[BUFFER];
                int n;
                while ((n = in.read(buf)) != -1) {
                    expanded += n;
                    if (expanded > MAX_UNCOMPRESSED) throw new SecurityException("Uncompressed database too large");
                    out.write(buf, 0, n);
                }
                out.getFD().sync();
            }
            try (SQLiteDatabase db = SQLiteDatabase.openDatabase(staging.getPath(), null, SQLiteDatabase.OPEN_READONLY);
                 Cursor integrity = db.rawQuery("PRAGMA integrity_check", null);
                 Cursor count = db.rawQuery("SELECT count(*) FROM docs", null);
                 Cursor ver = db.rawQuery("SELECT value FROM meta WHERE key='version'", null)) {
                if (!integrity.moveToFirst() || !"ok".equals(integrity.getString(0)))
                    throw new SecurityException("SQLite integrity check failed");
                if (!count.moveToFirst() || count.getInt(0) != m.getInt("documents"))
                    throw new SecurityException("Instruction count mismatch");
                if (!ver.moveToFirst() || !m.getString("version").equals(ver.getString(0)))
                    throw new SecurityException("Database version mismatch");
            }
            if (previous.exists() && !previous.delete()) throw new IllegalStateException("Cannot remove old backup");
            if (target.exists() && !target.renameTo(previous)) throw new IllegalStateException("Cannot preserve old database");
            if (!staging.renameTo(target)) {
                if (previous.exists()) previous.renameTo(target);
                throw new IllegalStateException("Cannot activate database");
            }
            previous.delete();
            return m.getString("version");
        } finally {
            archive.delete();
            staging.delete();
        }
    }
}
