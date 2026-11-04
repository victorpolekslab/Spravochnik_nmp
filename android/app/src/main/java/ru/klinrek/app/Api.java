package ru.klinrek.app;

import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.webkit.JavascriptInterface;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.Inflater;

/** Data access exposed to the WebView UI as window.Native. All methods return JSON strings. */
public class Api {
    private final SQLiteDatabase db;
    private final SQLiteDatabase udb;
    private final Notifier notifier;
    private static final Locale RU = new Locale("ru");

    interface Notifier { void js(String script); }

    Api(File f, File userDb, Notifier n) {
        db = SQLiteDatabase.openDatabase(f.getPath(), null, SQLiteDatabase.OPEN_READONLY);
        udb = SQLiteDatabase.openOrCreateDatabase(userDb, null);
        udb.execSQL("CREATE TABLE IF NOT EXISTS dl_cr(cr TEXT PRIMARY KEY, at TEXT, bytes INTEGER)");
        udb.execSQL("CREATE TABLE IF NOT EXISTS dl_sec(cr TEXT, ord INTEGER, sid TEXT, title TEXT, lvl INTEGER, html BLOB)");
        udb.execSQL("CREATE INDEX IF NOT EXISTS dl_sec_cr ON dl_sec(cr, ord)");
        notifier = n;
    }

    void close() {
        db.close();
        udb.close();
    }

    // ------------------------------------------------------------ Downloaded guidelines
    private static String q(String s) { return JSONObject.quote(s == null ? "" : s); }

    private boolean isOffline(String id) {
        Cursor c = db.rawQuery("SELECT 1 FROM sec WHERE cr=? LIMIT 1", new String[]{id});
        boolean r = c.moveToFirst(); c.close(); return r;
    }

    private boolean isDownloaded(String id) {
        Cursor c = udb.rawQuery("SELECT 1 FROM dl_cr WHERE cr=? LIMIT 1", new String[]{id});
        boolean r = c.moveToFirst(); c.close(); return r;
    }

    @JavascriptInterface
    public String dlList() {
        try {
            return rows(udb.rawQuery("SELECT cr, at, bytes FROM dl_cr ORDER BY at DESC", null)).toString();
        } catch (Exception e) {
            return err(e);
        }
    }

    @JavascriptInterface
    public String crInfo(String id) {
        try {
            JSONArray m = rows(db.rawQuery("SELECT id, code, version, name, age, ass, pub, mkb FROM cr WHERE id=?", new String[]{id}));
            if (m.length() == 0) return "{}";
            JSONObject o = m.getJSONObject(0);
            o.put("off", isOffline(id));
            o.put("dl", isDownloaded(id));
            return o.toString();
        } catch (Exception e) {
            return err(e);
        }
    }

    @JavascriptInterface
    public void download(final String id) {
        new Thread(() -> {
            try {
                String json = Downloader.fetch(id, bytes -> notifier.js("window.onDlProgress&&onDlProgress(" + q(id) + "," + bytes + ")"));
                java.util.List<Downloader.Section> secs = Downloader.parse(json);
                if (secs.isEmpty()) throw new Exception("в ответе нет разделов");
                long total = 0;
                udb.beginTransaction();
                try {
                    udb.delete("dl_sec", "cr=?", new String[]{id});
                    for (Downloader.Section sec : secs) {
                        android.content.ContentValues v = new android.content.ContentValues();
                        v.put("cr", id); v.put("ord", sec.ord); v.put("sid", sec.sid); v.put("title", sec.title); v.put("lvl", sec.lvl);
                        v.put("html", deflate(sec.html));
                        total += sec.html.length();
                        udb.insert("dl_sec", null, v);
                    }
                    android.content.ContentValues v = new android.content.ContentValues();
                    v.put("cr", id); v.put("at", new java.text.SimpleDateFormat("yyyy-MM-dd", Locale.ROOT).format(new java.util.Date())); v.put("bytes", total);
                    udb.insertWithOnConflict("dl_cr", null, v, SQLiteDatabase.CONFLICT_REPLACE);
                    udb.setTransactionSuccessful();
                } finally {
                    udb.endTransaction();
                }
                notifier.js("window.onDl&&onDl(" + q(id) + ",true,'')");
            } catch (Exception e) {
                String msg = e.getMessage() == null ? e.toString() : e.getMessage();
                if (e instanceof java.net.UnknownHostException || e instanceof java.net.ConnectException || e instanceof java.net.SocketTimeoutException)
                    msg = "нет связи с сервером cr.minzdrav.gov.ru";
                notifier.js("window.onDl&&onDl(" + q(id) + ",false," + q(msg) + ")");
            }
        }).start();
    }

    @JavascriptInterface
    public String dlDelete(String id) {
        udb.delete("dl_sec", "cr=?", new String[]{id});
        udb.delete("dl_cr", "cr=?", new String[]{id});
        return "{}";
    }

    static byte[] deflate(String s) {
        java.util.zip.Deflater d = new java.util.zip.Deflater(6);
        byte[] in = s.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        d.setInput(in); d.finish();
        ByteArrayOutputStream out = new ByteArrayOutputStream(in.length / 3 + 64);
        byte[] buf = new byte[1 << 15];
        while (!d.finished()) { int n = d.deflate(buf); out.write(buf, 0, n); }
        d.end();
        return out.toByteArray();
    }

    static String norm(String s) {
        if (s == null) return "";
        return s.toLowerCase(RU).replace('ё', 'е').replaceAll("\\s+", " ").trim();
    }

    private static final String RU_KEYS = "йцукенгшщзфывапролдячсмитьхъжэбю";
    private static final String EN_KEYS = "qwertyuiopasdfghjklzxcvbnm[];',.";

    /** Turns user input into an MKB code if it looks like one (handles Russian keyboard layout). */
    static String asCode(String q) {
        String s = q.trim().toLowerCase(RU).replace(',', '.').replace(" ", "");
        if (s.isEmpty()) return null;
        char c = s.charAt(0);
        int i = RU_KEYS.indexOf(c);
        if (i >= 0 && i < 26 && s.length() > 1 && Character.isDigit(s.charAt(1))) {
            s = EN_KEYS.charAt(i) + s.substring(1);
        }
        s = s.toUpperCase(Locale.ROOT);
        if (!s.matches("[A-Z][0-9]{0,2}(\\.?[0-9]{0,2})?")) return null;
        if (s.length() > 3 && s.charAt(3) != '.') s = s.substring(0, 3) + "." + s.substring(3);
        return s;
    }

    private JSONArray rows(Cursor c) throws Exception {
        JSONArray a = new JSONArray();
        try {
            String[] cols = c.getColumnNames();
            while (c.moveToNext()) {
                JSONObject o = new JSONObject();
                for (int i = 0; i < cols.length; i++) {
                    switch (c.getType(i)) {
                        case Cursor.FIELD_TYPE_INTEGER: o.put(cols[i], c.getLong(i)); break;
                        case Cursor.FIELD_TYPE_FLOAT: o.put(cols[i], c.getDouble(i)); break;
                        case Cursor.FIELD_TYPE_NULL: o.put(cols[i], JSONObject.NULL); break;
                        default: o.put(cols[i], c.getString(i));
                    }
                }
                a.put(o);
            }
        } finally {
            c.close();
        }
        return a;
    }

    private String err(Exception e) {
        try {
            return new JSONObject().put("error", String.valueOf(e)).toString();
        } catch (Exception x) {
            return "{\"error\":\"?\"}";
        }
    }

    @JavascriptInterface
    public String info() {
        try {
            JSONObject o = new JSONObject();
            Cursor c = db.rawQuery("SELECT k, v FROM meta", null);
            while (c.moveToNext()) o.put(c.getString(0), c.getString(1));
            c.close();
            return o.toString();
        } catch (Exception e) {
            return err(e);
        }
    }

    // ------------------------------------------------------------ MKB-10
    @JavascriptInterface
    public String mkbChildren(long parent) {
        try {
            Cursor c = parent <= 0
                    ? db.rawQuery("SELECT id, code, name, nchild, ncr FROM mkb WHERE parent IS NULL ORDER BY sort", null)
                    : db.rawQuery("SELECT id, code, name, nchild, ncr FROM mkb WHERE parent=? ORDER BY sort",
                    new String[]{String.valueOf(parent)});
            return rows(c).toString();
        } catch (Exception e) {
            return err(e);
        }
    }

    @JavascriptInterface
    public String mkbNode(long id) {
        try {
            JSONObject o = new JSONObject();
            JSONArray self = rows(db.rawQuery("SELECT id, code, name, parent, nchild, ncr, orig FROM mkb WHERE id=?",
                    new String[]{String.valueOf(id)}));
            if (self.length() == 0) return "{}";
            JSONObject n = self.getJSONObject(0);
            o.put("node", n);
            // path to root
            JSONArray path = new JSONArray();
            List<String> ancestorCodes = new ArrayList<>();
            Object p = n.opt("parent");
            while (p != null && p != JSONObject.NULL) {
                JSONArray r = rows(db.rawQuery("SELECT id, code, name, parent FROM mkb WHERE id=?",
                        new String[]{String.valueOf(p)}));
                if (r.length() == 0) break;
                JSONObject x = r.getJSONObject(0);
                path.put(x);
                ancestorCodes.add(x.getString("code"));
                p = x.opt("parent");
            }
            JSONArray rev = new JSONArray();
            for (int i = path.length() - 1; i >= 0; i--) rev.put(path.get(i));
            o.put("path", rev);
            o.put("children", new JSONArray(mkbChildren(id)));
            // guidelines are shown at the code they list and below it (ancestor codes);
            // a 3-character category (J45) also shows guidelines listed for its subcodes (J45.0 ...)
            String code = n.optString("code", "");
            List<String> args = new ArrayList<>();
            StringBuilder own = new StringBuilder("?");
            args.add(code);
            for (String a : ancestorCodes) {
                own.append(",?");
                args.add(a);
            }
            boolean cat = code.matches("[A-Z]\\d\\d");
            args.add(cat ? "1" : "0");
            args.add(code + ".%");
            String sql = "SELECT cr.id, cr.code, cr.version, cr.name, cr.age, cr.pub, "
                    + "EXISTS(SELECT 1 FROM sec WHERE sec.cr=cr.id) AS off, "
                    + "group_concat(DISTINCT cm.code) AS via FROM cr_mkb cm JOIN cr ON cr.id=cm.cr "
                    + "WHERE cm.code IN (" + own + ") OR (? = '1' AND cm.code LIKE ?) "
                    + "GROUP BY cr.id ORDER BY cr.name";
            o.put("cr", rows(db.rawQuery(sql, args.toArray(new String[0]))));
            return o.toString();
        } catch (Exception e) {
            return err(e);
        }
    }

    @JavascriptInterface
    public String mkbSearch(String q) {
        try {
            JSONObject o = new JSONObject();
            String code = asCode(q);
            JSONArray res;
            if (code != null) {
                o.put("code", code);
                res = rows(db.rawQuery("SELECT id, code, name, nchild, ncr FROM mkb WHERE code LIKE ? "
                        + "ORDER BY length(code), code LIMIT 300", new String[]{code + "%"}));
            } else {
                String[] words = norm(q).split(" ");
                StringBuilder w = new StringBuilder();
                List<String> args = new ArrayList<>();
                for (String s : words) {
                    if (s.isEmpty()) continue;
                    if (w.length() > 0) w.append(" AND ");
                    w.append("q LIKE ?");
                    args.add("%" + s + "%");
                }
                if (args.isEmpty()) return "{\"items\":[]}";
                res = rows(db.rawQuery("SELECT id, code, name, nchild, ncr FROM mkb WHERE " + w
                        + " ORDER BY CASE WHEN code LIKE '%-%' OR parent IS NULL THEN 0 ELSE 1 END, sort LIMIT 300",
                        args.toArray(new String[0])));
            }
            o.put("items", res);
            return o.toString();
        } catch (Exception e) {
            return err(e);
        }
    }

    // ------------------------------------------------------------ Guidelines
    @JavascriptInterface
    public String crList() {
        try {
            JSONObject o = new JSONObject();
            o.put("items", rows(db.rawQuery("SELECT id, code, version, name, age, pub, mkb, cls, q, EXISTS(SELECT 1 FROM sec WHERE sec.cr=cr.id) AS off FROM cr ORDER BY name", null)));
            o.put("classes", rows(db.rawQuery("SELECT id, code, name FROM mkb WHERE parent IS NULL ORDER BY sort", null)));
            return o.toString();
        } catch (Exception e) {
            return err(e);
        }
    }

    @JavascriptInterface
    public String crDoc(String id) {
        try {
            JSONObject o = new JSONObject();
            JSONArray m = rows(db.rawQuery("SELECT id, code, version, name, age, ass, pub, mkb FROM cr WHERE id=?",
                    new String[]{id}));
            if (m.length() == 0) return "{}";
            o.put("meta", m.getJSONObject(0));
            JSONArray secs = new JSONArray();
            Cursor c = isOffline(id)
                    ? db.rawQuery("SELECT id, ord, sid, title, lvl, html FROM sec WHERE cr=? ORDER BY ord", new String[]{id})
                    : udb.rawQuery("SELECT rowid AS id, ord, sid, title, lvl, html FROM dl_sec WHERE cr=? ORDER BY ord", new String[]{id});
            try {
                while (c.moveToNext()) {
                    JSONObject s = new JSONObject();
                    s.put("id", c.getLong(0));
                    s.put("ord", c.getInt(1));
                    s.put("sid", c.getString(2));
                    s.put("title", c.getString(3));
                    s.put("lvl", c.getInt(4));
                    byte[] z = c.isNull(5) ? null : c.getBlob(5);
                    s.put("html", z == null ? "" : inflate(z));
                    secs.put(s);
                }
            } finally {
                c.close();
            }
            o.put("sections", secs);
            o.put("off", isOffline(id));
            o.put("dl", isDownloaded(id));
            // MKB names for the codes
            o.put("mkb", rows(db.rawQuery("SELECT cm.code, (SELECT name FROM mkb WHERE code=cm.code LIMIT 1) AS name, "
                    + "(SELECT id FROM mkb WHERE code=cm.code LIMIT 1) AS mid FROM cr_mkb cm WHERE cr=? ORDER BY cm.code", new String[]{id})));
            return o.toString();
        } catch (Exception e) {
            return err(e);
        }
    }

    @JavascriptInterface
    public String crSumm(String id) {
        try {
            JSONObject o = new JSONObject();
            JSONArray m = rows(db.rawQuery("SELECT id, code, version, name, age, ass, pub, mkb FROM cr WHERE id=?",
                    new String[]{id}));
            if (m.length() == 0) return "{}";
            o.put("meta", m.getJSONObject(0));
            Cursor c = db.rawQuery("SELECT data FROM summ WHERE cr=?", new String[]{id});
            try {
                o.put("summ", c.moveToFirst() && !c.isNull(0) ? new JSONObject(inflate(c.getBlob(0))) : new JSONObject());
            } finally {
                c.close();
            }
            o.put("mkb", rows(db.rawQuery("SELECT cm.code, (SELECT name FROM mkb WHERE code=cm.code LIMIT 1) AS name, "
                    + "(SELECT id FROM mkb WHERE code=cm.code LIMIT 1) AS mid FROM cr_mkb cm WHERE cr=? ORDER BY cm.code", new String[]{id})));
            return o.toString();
        } catch (Exception e) {
            return err(e);
        }
    }

    static String inflate(byte[] z) throws Exception {
        Inflater inf = new Inflater();
        inf.setInput(z);
        ByteArrayOutputStream out = new ByteArrayOutputStream(z.length * 4);
        byte[] buf = new byte[1 << 15];
        while (!inf.finished()) {
            int n = inf.inflate(buf);
            if (n == 0 && (inf.needsInput() || inf.needsDictionary())) break;
            out.write(buf, 0, n);
        }
        inf.end();
        return out.toString("UTF-8");
    }

    // ------------------------------------------------------------ Full-text search
    private static final Pattern TAGS = Pattern.compile("<[^>]+>");

    static String plain(String html) {
        String t = TAGS.matcher(html).replaceAll(" ");
        t = t.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"")
                .replace("&amp;", "&");
        return t.replaceAll("\\s+", " ").trim();
    }

    // Light Russian ending stripper so that "томография" also finds "томографии" (used as a prefix).
    private static final String[] ENDINGS;
    static {
        String[] e = ("иями ями ами ого его ему ому ыми ими ая яя ое ее ые ие ый ий ой ей ую юю ых их ом ем ам ям ах ях "
                + "ия ии ию ья ье ью ов ев а я о е ы и у ю ь й").split(" ");
        java.util.Arrays.sort(e, (a, b) -> b.length() - a.length());
        ENDINGS = e;
    }

    static String stem(String w) {
        if (w.length() < 4) return w;
        for (int i = 0; i < w.length(); i++) if (!Character.isLetter(w.charAt(i))) return w;
        for (String e : ENDINGS) {
            if (w.endsWith(e) && w.length() - e.length() >= 3) return w.substring(0, w.length() - e.length());
        }
        return w;
    }

    /** Search terms: normalized words, endings stripped; each is used as a prefix. */
    static List<String> terms(String q) {
        List<String> t = new ArrayList<>();
        for (String w : norm(q).split("[^\\p{L}\\p{N}]+")) {
            if (w.length() >= 2 || (w.length() == 1 && Character.isDigit(w.charAt(0)))) {
                String s = stem(w);
                if (!t.contains(s)) t.add(s);
            }
        }
        return t;
    }

    private static final String W = "[\\p{L}\\p{N}]*";

    static Pattern phrasePattern(List<String> t) {
        StringBuilder b = new StringBuilder("(?<![\\p{L}\\p{N}])");
        for (int i = 0; i < t.size(); i++) {
            if (i > 0) b.append("[^\\p{L}\\p{N}]+");
            b.append(Pattern.quote(t.get(i))).append(W);
        }
        return Pattern.compile(b.toString());
    }

    @JavascriptInterface
    public String search(String q, String filterCr) {
        try {
            List<String> t = terms(q);
            JSONObject o = new JSONObject();
            o.put("terms", new JSONArray(t));
            if (t.isEmpty()) {
                o.put("groups", new JSONArray());
                return o.toString();
            }
            StringBuilder m = new StringBuilder();
            for (String w : t) {
                if (m.length() > 0) m.append(' ');
                m.append(w.replace("\"", "")).append('*');
            }
            boolean flt = filterCr != null && !filterCr.isEmpty();
            // sections where the words stand together as a phrase rank first
            java.util.Set<Long> phrase = new java.util.HashSet<>();
            if (t.size() > 1) {
                String pq = "\"" + m + "\"";
                Cursor pc = db.rawQuery("SELECT fts.rowid FROM fts" + (flt ? " JOIN sec s ON s.id=fts.rowid" : "")
                        + " WHERE fts MATCH ?" + (flt ? " AND s.cr=?" : ""),
                        flt ? new String[]{pq, filterCr} : new String[]{pq});
                try {
                    while (pc.moveToNext()) phrase.add(pc.getLong(0));
                } finally {
                    pc.close();
                }
            }
            String sql = "SELECT s.id, s.cr, s.title, s.ord, cr.name, cr.code, cr.version, cr.age "
                    + "FROM fts JOIN sec s ON s.id=fts.rowid JOIN cr ON cr.id=s.cr WHERE fts MATCH ?"
                    + (flt ? " AND s.cr=?" : "")
                    + " ORDER BY s.cr, s.ord LIMIT 8000";
            String[] args = flt ? new String[]{m.toString(), filterCr} : new String[]{m.toString()};
            Map<String, JSONObject> groups = new LinkedHashMap<>();
            Map<String, List<JSONObject>> secs = new LinkedHashMap<>();
            Cursor c = db.rawQuery(sql, args);
            int total = 0;
            try {
                while (c.moveToNext()) {
                    total++;
                    String cr = c.getString(1);
                    JSONObject g = groups.get(cr);
                    if (g == null) {
                        g = new JSONObject();
                        g.put("cr", cr);
                        g.put("name", c.getString(4));
                        g.put("code", c.getInt(5));
                        g.put("version", c.getInt(6));
                        g.put("age", c.getInt(7));
                        String nn = norm(c.getString(4));
                        boolean all = true;
                        for (String w : t) if (!nn.contains(w)) all = false;
                        g.put("score", all ? 5000 : 0);
                        g.put("nphr", 0);
                        groups.put(cr, g);
                        secs.put(cr, new ArrayList<>());
                    }
                    long sid = c.getLong(0);
                    boolean ph = phrase.contains(sid);
                    JSONObject s = new JSONObject();
                    s.put("id", sid);
                    s.put("title", c.getString(2));
                    s.put("ord", c.getInt(3));
                    s.put("ph", ph);
                    secs.get(cr).add(s);
                    g.put("score", g.getInt("score") + (ph ? 100 : 1));
                    if (ph) g.put("nphr", g.getInt("nphr") + 1);
                }
            } finally {
                c.close();
            }
            List<JSONObject> list = new ArrayList<>(groups.values());
            list.sort((a, b) -> Integer.compare(b.optInt("score"), a.optInt("score")));
            JSONArray out = new JSONArray();
            Pattern pp = phrasePattern(t);
            int k = 0;
            for (JSONObject g : list) {
                List<JSONObject> ss = secs.get(g.getString("cr"));
                ss.sort((a, b) -> {
                    int x = Boolean.compare(b.optBoolean("ph"), a.optBoolean("ph"));
                    return x != 0 ? x : Integer.compare(a.optInt("ord"), b.optInt("ord"));
                });
                g.put("nsec", ss.size());
                JSONArray keep = new JSONArray();
                for (int i = 0; i < ss.size() && i < 4; i++) {
                    JSONObject s = ss.get(i);
                    if (k < 120) s.put("snip", snippet(s.getLong("id"), t, pp));
                    keep.put(s);
                }
                k++;
                g.put("sections", keep);
                out.put(g);
            }
            o.put("total", total);
            o.put("groups", out);
            return o.toString();
        } catch (Exception e) {
            return err(e);
        }
    }

    private String snippet(long secId, List<String> t, Pattern phrase) {
        try {
            Cursor c = db.rawQuery("SELECT html FROM sec WHERE id=?", new String[]{String.valueOf(secId)});
            String html = "";
            if (c.moveToFirst() && !c.isNull(0)) html = inflate(c.getBlob(0));
            c.close();
            String text = plain(html);
            String low = text.toLowerCase(RU).replace('ё', 'е');
            int best = -1;
            if (t.size() > 1) {
                Matcher pm = phrase.matcher(low);
                if (pm.find()) best = pm.start();
            }
            if (best < 0) {
                for (String w : t) {
                    Matcher mm = Pattern.compile("(?<![\\p{L}\\p{N}])" + Pattern.quote(w)).matcher(low);
                    if (mm.find() && (best < 0 || mm.start() < best)) best = mm.start();
                }
            }
            if (best < 0) return text.length() > 160 ? text.substring(0, 160) + "…" : text;
            int a = Math.max(0, best - 70), b = Math.min(text.length(), best + 150);
            while (a > 0 && a < best && !Character.isWhitespace(text.charAt(a - 1))) a++;
            return (a > 0 ? "…" : "") + text.substring(a, b) + (b < text.length() ? "…" : "");
        } catch (Exception e) {
            return "";
        }
    }
}
