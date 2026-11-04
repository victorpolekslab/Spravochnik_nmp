package ru.klinrek.app;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Downloads a guideline from the official rubricator API and turns it into clean, image-free HTML sections. */
final class Downloader {
    static final String API = "https://apicr.minzdrav.gov.ru/api.ashx?op=GetClinrec2&id=";

    static final class Section {
        final int ord; final String sid, title, html; final int lvl;
        Section(int ord, String sid, String title, int lvl, String html) {
            this.ord = ord; this.sid = sid; this.title = title; this.lvl = lvl; this.html = html;
        }
    }

    interface Progress { void on(long bytes); }

    static String fetch(String id, Progress p) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(API + id).openConnection();
        c.setConnectTimeout(20000);
        c.setReadTimeout(120000);
        c.setRequestProperty("Accept", "application/json");
        int code = c.getResponseCode();
        if (code != 200) throw new Exception("сервер ответил " + code);
        ByteArrayOutputStream out = new ByteArrayOutputStream(1 << 20);
        try (InputStream in = c.getInputStream()) {
            byte[] buf = new byte[1 << 16];
            int n; long total = 0, last = 0;
            while ((n = in.read(buf)) > 0) {
                out.write(buf, 0, n);
                total += n;
                if (p != null && total - last > 256 * 1024) { last = total; p.on(total); }
            }
        } finally {
            c.disconnect();
        }
        return new String(out.toByteArray(), StandardCharsets.UTF_8);
    }

    private static final Pattern DATA_URI = Pattern.compile("data:image/[a-zA-Z+]+;base64,[A-Za-z0-9+/=\\s]+");

    static List<Section> parse(String json) throws Exception {
        json = DATA_URI.matcher(json).replaceAll("");
        JSONObject d = new JSONObject(json);
        JSONArray secs = d.getJSONObject("obj").getJSONArray("sections");
        List<Section> out = new ArrayList<>();
        int ord = 0;
        for (int i = 0; i < secs.length(); i++) {
            JSONObject s = secs.getJSONObject(i);
            String sid = s.optString("id", "");
            if ("doc_whole".equals(sid) || "doc_title".equals(sid)) continue;
            String title = s.optString("title", "").trim();
            String html = s.isNull("content") ? "" : clean(s.optString("content", ""));
            int lvl = title.matches("^\\d+\\.\\d+.*") ? 2 : 1;
            out.add(new Section(ord++, sid, title, lvl, html));
        }
        return out;
    }

    // ---------------------------------------------------------------- HTML cleaning (regex, no parser dependency)
    private static final String IMG_PH = "<div class=\"imgph\">Иллюстрация — см. оригинал (кнопка «Сайт» или «PDF»)</div>";
    private static final Pattern COMMENTS = Pattern.compile("<!--.*?-->", Pattern.DOTALL);
    private static final Pattern DROP = Pattern.compile("<(script|style|xml|head|title|object|iframe|svg)\\b[^>]*>.*?</\\1\\s*>", Pattern.DOTALL | Pattern.CASE_INSENSITIVE);
    private static final Pattern IMG = Pattern.compile("<img\\b[^>]*>", Pattern.CASE_INSENSITIVE);
    private static final Pattern NS_TAG = Pattern.compile("</?[a-zA-Z]+:[a-zA-Z]+\\b[^>]*>");
    private static final Pattern TAG = Pattern.compile("<(/?)([a-zA-Z][a-zA-Z0-9]*)\\b([^>]*)>");
    private static final Pattern ATTR = Pattern.compile("([a-zA-Z-]+)\\s*=\\s*(\"[^\"]*\"|'[^']*'|[^\\s>]+)");
    private static final Set<String> KEEP = new HashSet<>(java.util.Arrays.asList(
            "p", "br", "strong", "b", "em", "i", "u", "sup", "sub", "ul", "ol", "li", "table", "thead", "tbody",
            "tfoot", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "caption", "hr"));
    private static final Pattern EMPTY = Pattern.compile("<(p|li|strong|b|em|i|u|sup|sub)>(\\s|&nbsp;|\u00a0)*</\\1>");
    private static final String MARK = "\u0001IMG\u0001";

    static String clean(String html) {
        if (html == null || html.trim().isEmpty()) return "";
        String s = COMMENTS.matcher(html).replaceAll("");
        s = DROP.matcher(s).replaceAll("");
        s = IMG.matcher(s).replaceAll(MARK);
        s = NS_TAG.matcher(s).replaceAll("");
        Matcher m = TAG.matcher(s);
        StringBuffer sb = new StringBuffer(s.length());
        while (m.find()) {
            String close = m.group(1), name = m.group(2).toLowerCase(Locale.ROOT), attrs = m.group(3);
            String rep;
            if (!KEEP.contains(name)) {
                rep = "";
            } else if (!close.isEmpty()) {
                rep = "</" + name + ">";
            } else {
                StringBuilder a = new StringBuilder();
                Matcher am = ATTR.matcher(attrs == null ? "" : attrs);
                while (am.find()) {
                    String k = am.group(1).toLowerCase(Locale.ROOT);
                    String v = am.group(2).replaceAll("^[\"']|[\"']$", "");
                    if ((k.equals("colspan") || k.equals("rowspan")) && v.matches("\\d+") && Integer.parseInt(v) > 1) {
                        a.append(' ').append(k).append("=\"").append(v).append('"');
                    }
                }
                rep = "<" + name + a + (attrs != null && attrs.trim().endsWith("/") && name.equals("br") ? "/" : "") + ">";
            }
            m.appendReplacement(sb, Matcher.quoteReplacement(rep));
        }
        m.appendTail(sb);
        s = sb.toString();
        for (int i = 0; i < 3; i++) s = EMPTY.matcher(s).replaceAll("");
        s = s.replace(MARK, IMG_PH);
        s = s.replaceAll("(\\s*<br/?>\\s*){3,}", "<br/><br/>");
        s = s.replaceAll("[ \\t\\r\\n]+", " ").trim();
        return s;
    }
}
