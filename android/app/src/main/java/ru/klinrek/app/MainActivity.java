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
        });
        setContentView(web);
        web.loadUrl("file:///android_asset/www/index.html");
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
