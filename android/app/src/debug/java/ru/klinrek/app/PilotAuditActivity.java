package ru.klinrek.app;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.net.Uri;
import java.io.ByteArrayInputStream;

/** Debug source-set only. The test WebView has no native interfaces. */
public final class PilotAuditActivity extends Activity {
    @Override protected void onStop() {
        android.webkit.CookieManager.getInstance().flush();
        super.onStop();
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        int port = getIntent().getIntExtra("pilotPort", 0);
        if (port < 1024 || port > 65535) { finish(); return; }
        WebView.setWebContentsDebuggingEnabled(true);
        WebView view = new WebView(this);
        view.getSettings().setJavaScriptEnabled(true);
        view.getSettings().setDomStorageEnabled(true);
        view.getSettings().setAllowFileAccess(false);
        view.getSettings().setAllowContentAccess(false);
        view.setWebViewClient(new WebViewClient() {
            private boolean loopback(Uri uri) {
                return "http".equals(uri.getScheme()) && "localhost".equals(uri.getHost())
                    && uri.getPort() == port && uri.getUserInfo() == null;
            }
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                return !loopback(r.getUrl());
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest r) {
                return loopback(r.getUrl()) ? null
                    : new WebResourceResponse("text/plain", "UTF-8", new ByteArrayInputStream(new byte[0]));
            }
        });
        setContentView(view);
        view.loadUrl("http://localhost:" + port + "/#learn");
    }
}
