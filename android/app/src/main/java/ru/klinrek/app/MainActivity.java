package ru.klinrek.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

public class MainActivity extends Activity {
    static final String DB_NAME = "cr.db";
    // bump together with the bundled database
    static final int DB_VERSION = BuildConfigHolder.DB_VERSION;

    private WebView web;
    private Api api;
    private TextView status;
    private ProgressBar bar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String h = getIntent() != null ? getIntent().getStringExtra("hash") : null;
        if (h != null && h.matches("#[a-z]+")) pendingHash = h;
        File db = getDatabasePath(DB_NAME);
        SharedPreferences sp = getSharedPreferences("app", MODE_PRIVATE);
        if (db.exists() && sp.getInt("dbv", 0) == DB_VERSION) {
            startUi(db);
        } else {
            showSplash();
            new Thread(() -> {
                try {
                    copyDb(db);
                    sp.edit().putInt("dbv", DB_VERSION).apply();
                    new Handler(Looper.getMainLooper()).post(() -> startUi(db));
                } catch (Exception e) {
                    new Handler(Looper.getMainLooper()).post(() ->
                            status.setText("Не удалось подготовить базу: " + e.getMessage()
                                    + "\nПроверьте свободное место (нужно около 400 МБ)."));
                }
            }).start();
        }
    }

    private void showSplash() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        l.setGravity(Gravity.CENTER);
        l.setPadding(64, 64, 64, 64);
        TextView t = new TextView(this);
        t.setText("Справочник фельдшера неотложной медицинской помощи");
        t.setTextSize(22);
        t.setGravity(Gravity.CENTER);
        status = new TextView(this);
        status.setText("Первый запуск: подготавливаю справочник…");
        status.setGravity(Gravity.CENTER);
        status.setPadding(0, 32, 0, 32);
        bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        bar.setMax(100);
        l.addView(t);
        l.addView(status);
        l.addView(bar, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));
        setContentView(l);
    }

    private void copyDb(File db) throws Exception {
        db.getParentFile().mkdirs();
        File tmp = new File(db.getPath() + ".tmp");
        long total;
        try (java.io.DataInputStream sz = new java.io.DataInputStream(getAssets().open("cr.db.size"))) {
            total = Long.parseLong(new java.util.Scanner(sz).nextLine().trim());
        } catch (Exception e) {
            total = 1;
        }
        try (InputStream in = getAssets().open(DB_NAME); OutputStream out = new FileOutputStream(tmp)) {
            byte[] buf = new byte[1 << 16];
            long done = 0;
            int n, lastPct = -1;
            while ((n = in.read(buf)) > 0) {
                out.write(buf, 0, n);
                done += n;
                int pct = (int) (done * 100 / Math.max(total, 1));
                if (pct != lastPct && bar != null) {
                    lastPct = pct;
                    final int p = Math.min(pct, 100);
                    runOnUiThread(() -> bar.setProgress(p));
                }
            }
        }
        new File(db.getPath() + "-journal").delete();
        if (db.exists()) db.delete();
        if (!tmp.renameTo(db)) throw new Exception("rename failed");
    }

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    private void startUi(File db) {
        web = new WebView(this);
        api = new Api(db, getDatabasePath("user.db"), script -> runOnUiThread(() -> { if (web != null) web.evaluateJavascript(script, null); }));
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setTextZoom(100);
        s.setBuiltInZoomControls(false);
        web.setBackgroundColor(Color.TRANSPARENT);
        web.addJavascriptInterface(api, "Native");
        web.addJavascriptInterface(new AppBridge(), "App");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                String sch = u.getScheme();
                if ("http".equals(sch) || "https".equals(sch)) {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, u));
                    } catch (Exception ignored) {
                    }
                    return true;
                }
                return false;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                if (!updateChecked) { updateChecked = true; checkUpdate(false); checkContent(); }
                if (pendingHash != null) { view.evaluateJavascript("location.hash=" + org.json.JSONObject.quote(pendingHash), null); pendingHash = null; }
            }
        });
        setContentView(web);
        web.loadUrl(Ota.startUrl(this));
    }

    // ------------------------------------------------------------ update check
    static final String UPDATE_URL = "https://victorpolekslab.github.io/Spravochnik_nmp/android.json";
    private boolean updateChecked = false;
    private long lastCheck = 0;

    /** Exposed to the page as window.App (the web version provides the same object). */
    public class AppBridge {
        @android.webkit.JavascriptInterface
        public void checkUpdate() { MainActivity.this.checkUpdate(true); }
        /** Страница стартовала нормально — скачанная версия содержимого рабочая. */
        @android.webkit.JavascriptInterface
        public void otaOk() { Ota.ok(MainActivity.this); }
        /** Версия содержимого, которая сейчас запущена (из APK или скачанная). */
        @android.webkit.JavascriptInterface
        public String contentVersion() { return String.valueOf(Ota.running(MainActivity.this)); }
        @android.webkit.JavascriptInterface
        public void checkContent() { MainActivity.this.checkContent(); }
        /** Слежение за новыми КР (включается при входе организатора). */
        @android.webkit.JavascriptInterface
        public void krWatch(boolean on) {
            boolean was = KrWatch.on(MainActivity.this);
            KrWatch.enable(MainActivity.this, on);
            if (on && !was && android.os.Build.VERSION.SDK_INT >= 33
                    && checkSelfPermission("android.permission.POST_NOTIFICATIONS") != android.content.pm.PackageManager.PERMISSION_GRANTED)
                runOnUiThread(() -> requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 1));
            if (on) KrWatch.maybeCheck(MainActivity.this, false, () -> js("window.onKrStatus&&onKrStatus()"));
        }
        @android.webkit.JavascriptInterface
        public String krStatus() {
            SharedPreferences p = KrWatch.sp(MainActivity.this);
            try {
                org.json.JSONObject o = new org.json.JSONObject().put("on", p.getBoolean("on", false)).put("at", p.getLong("at", 0))
                        .put("ok", p.getLong("ok", 0)).put("err", p.getString("err", ""));
                String r = p.getString("res", null);
                if (r != null) o.put("res", new org.json.JSONObject(r));
                return o.toString();
            } catch (Exception e) { return "{}"; }
        }
        @android.webkit.JavascriptInterface
        public void krCheck() { KrWatch.maybeCheck(MainActivity.this, true, () -> js("window.onKrStatus&&onKrStatus()")); }
    }

    /** Открыть раздел из уведомления (extra "hash", например #krnew). */
    private String pendingHash = null;

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        String h = intent.getStringExtra("hash");
        if (h != null && h.matches("#[a-z]+") && web != null) web.evaluateJavascript("location.hash=" + org.json.JSONObject.quote(h), null);
    }

    private void js(String script) {
        runOnUiThread(() -> { if (web != null) web.evaluateJavascript(script, null); });
    }

    /** Asks the site for the latest APK version; if it is newer, the page shows an "update available" banner.
     *  manual = from the "Проверить обновления" button: also report "up to date" / "no connection". */
    @SuppressWarnings("deprecation")
    private void checkUpdate(boolean manual) {
        lastCheck = System.currentTimeMillis();
        new Thread(() -> {
            try {
                // the query string bypasses the CDN cache, so a fresh release is seen at once
                java.net.HttpURLConnection c = (java.net.HttpURLConnection)
                        new java.net.URL(UPDATE_URL + "?t=" + System.currentTimeMillis()).openConnection();
                c.setConnectTimeout(10000);
                c.setReadTimeout(10000);
                c.setUseCaches(false);
                c.setRequestProperty("Cache-Control", "no-cache");
                if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
                java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
                try (InputStream in = c.getInputStream()) {
                    byte[] buf = new byte[8192]; int n;
                    while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
                } finally {
                    c.disconnect();
                }
                org.json.JSONObject o = new org.json.JSONObject(out.toString("UTF-8"));
                long latest = o.optLong("versionCode", 0);
                long current = getPackageManager().getPackageInfo(getPackageName(), 0).versionCode;
                if (latest > current) js("window.onUpdate&&onUpdate(" + o + ")");
                else if (manual) js("window.onUpdateNone&&onUpdateNone()");
            } catch (Exception e) {
                if (manual) js("window.onUpdateFail&&onUpdateFail()");
            }
        }).start();
    }

    // ------------------------------------------------------------ content updates (OTA)
    private long pausedAt = 0;

    private void checkContent() {
        Ota.check(this, () -> js("window.onContentReady&&onContentReady()"));
    }

    @Override
    protected void onPause() {
        super.onPause();
        pausedAt = System.currentTimeMillis();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web == null) return;
        // скачанное обновление содержимого применяем, если приложение было свёрнуто больше 10 минут
        if (pausedAt > 0 && System.currentTimeMillis() - pausedAt > 10 * 60 * 1000 && Ota.pending(this)) {
            web.loadUrl(Ota.startUrl(this));
            return;
        }
        // the app often stays in memory for days: check again when it comes back, at most every 30 minutes
        if (updateChecked && System.currentTimeMillis() - lastCheck > 30 * 60 * 1000) { checkUpdate(false); checkContent(); }
        KrWatch.maybeCheck(this, false, () -> js("window.onKrStatus&&onKrStatus()"));
    }

    @Override
    public void onBackPressed() {
        if (web != null) {
            web.evaluateJavascript("window.appBack ? appBack() : false", v -> {
                if (!"true".equals(v)) MainActivity.super.onBackPressed();
            });
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (api != null) api.close();
        super.onDestroy();
    }
}
