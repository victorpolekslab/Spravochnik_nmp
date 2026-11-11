package ru.klinrek.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.os.Build;

import org.json.JSONArray;
import org.json.JSONObject;
import org.json.JSONTokener;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/**
 * Слежение за рубрикатором КР (только для организатора): раз в сутки телефон запрашивает у Минздрава список
 * действующих КР и сравнивает его с базой приложения. Новые, обновлённые (выше версия) и отменённые КР
 * сохраняются в настройках; о каждой новой находке — системное уведомление.
 * Сайт Минздрава недоступен с зарубежных серверов, поэтому проверка идёт именно с телефона.
 */
public class KrWatch extends JobService {
    static final String[] URLS = {
            "https://apicr.minzdrav.gov.ru/api.ashx?op=GetJsonClinrecs",
            "https://apicr.minzdrav.gov.ru/api.ashx?op=GetJsonSpecialityClinrecs"};
    static final int JOB_ID = 7301;
    static final String CHANNEL = "kr_updates";
    private static volatile boolean busy = false;

    static SharedPreferences sp(Context c) { return c.getSharedPreferences("krwatch", Context.MODE_PRIVATE); }

    /** Включить/выключить слежение (вызывается со страницы: вход/выход организатора). */
    static void enable(Context c, boolean on) {
        sp(c).edit().putBoolean("on", on).apply();
        JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (js == null) return;
        if (!on) { js.cancel(JOB_ID); return; }
        if (js.getPendingJob(JOB_ID) != null) return;
        js.schedule(new JobInfo.Builder(JOB_ID, new ComponentName(c, KrWatch.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPeriodic(24L * 3600 * 1000)
                .setPersisted(false)
                .build());
    }

    static boolean on(Context c) { return sp(c).getBoolean("on", false); }

    /** Проверить, если включено и с прошлой проверки прошло больше 20 часов (или force). */
    static void maybeCheck(Context ctx, boolean force, Runnable done) {
        final Context c = ctx.getApplicationContext();
        if (!on(c) || busy) return;
        if (!force && System.currentTimeMillis() - sp(c).getLong("at", 0) < 20L * 3600 * 1000) return;
        busy = true;
        new Thread(() -> {
            try { check(c); } finally { busy = false; if (done != null) done.run(); }
        }).start();
    }

    @Override
    public boolean onStartJob(JobParameters params) {
        if (!on(this)) return false;
        new Thread(() -> {
            try { check(getApplicationContext()); } finally { jobFinished(params, false); }
        }).start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) { return true; }

    // ------------------------------------------------------------------ проверка
    static void check(Context c) {
        SharedPreferences p = sp(c);
        String err = "";
        Map<String, String[]> remote = null;
        for (String u : URLS) {
            try {
                String body = get(u);
                remote = parse(body);
                if (remote.size() >= 300) { saveList(c, body, u.replaceAll(".*op=", "")); break; }
                err = "в ответе " + u.replaceAll(".*op=", "") + " только " + remote.size() + " КР";
                remote = null;
            } catch (Exception e) {
                err = (e instanceof java.net.UnknownHostException || e instanceof java.net.ConnectException || e instanceof java.net.SocketTimeoutException)
                        ? "нет связи с cr.minzdrav.gov.ru" : String.valueOf(e.getMessage());
            }
        }
        p.edit().putLong("at", System.currentTimeMillis()).apply();
        if (remote == null) { p.edit().putString("err", err).apply(); return; }
        try {
            JSONObject res = diff(c, remote);
            p.edit().putString("err", "").putString("res", res.toString()).putLong("ok", System.currentTimeMillis()).apply();
            notifyNew(c, res);
        } catch (Exception e) {
            p.edit().putString("err", "сравнение: " + e.getMessage()).apply();
        }
    }

    /** id → {id, name, date}. Принимает любой из известных форматов ответа: ищет объекты с id вида 123_4. */
    static Map<String, String[]> parse(String body) throws Exception {
        Object root = new JSONTokener(body.trim()).nextValue();
        Map<String, String[]> out = new LinkedHashMap<>();
        walk(root, out, 0);
        return out;
    }

    private static String str(JSONObject o, String... keys) {
        for (String k : keys) {
            java.util.Iterator<String> it = o.keys();
            while (it.hasNext()) { String x = it.next(); if (x.equalsIgnoreCase(k) && !o.isNull(x)) return String.valueOf(o.opt(x)).trim(); }
        }
        return "";
    }

    private static void walk(Object v, Map<String, String[]> out, int depth) {
        if (depth > 6 || v == null) return;
        if (v instanceof JSONArray) {
            JSONArray a = (JSONArray) v;
            for (int i = 0; i < a.length(); i++) walk(a.opt(i), out, depth + 1);
        } else if (v instanceof JSONObject) {
            JSONObject o = (JSONObject) v;
            String id = str(o, "id", "Id", "ID");
            String name = str(o, "name", "Name");
            if (id.matches("\\d+_\\d+") && !name.isEmpty()) {
                String st = str(o, "apply_status", "ApplyStatus");
                String status = str(o, "status", "Status");
                boolean active = st.isEmpty() ? (status.isEmpty() || status.equals("0")) : st.toLowerCase().startsWith("примен");
                if (active) out.put(id, new String[]{id, name, date(str(o, "publish_date", "PublishDate", "pub"))});
                return;
            }
            java.util.Iterator<String> it = o.keys();
            while (it.hasNext()) walk(o.opt(it.next()), out, depth + 1);
        }
    }

    private static String date(String s) {   // "/Date(1604523600000)/" или ISO
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("Date\\((\\d+)").matcher(s);
        if (m.find()) return new java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.ROOT).format(new java.util.Date(Long.parseLong(m.group(1))));
        return s.length() >= 10 ? s.substring(0, 10) : s;
    }

    /** Сравнение с базой приложения: new — нового кода нет в базе; upd — у кода версия выше; gone — в базе есть, на сайте нет. */
    static JSONObject diff(Context c, Map<String, String[]> remote) throws Exception {
        File dbf = c.getDatabasePath(MainActivity.DB_NAME);
        Map<Integer, Integer> localVer = new HashMap<>();
        Map<Integer, String[]> localRow = new HashMap<>();
        try (SQLiteDatabase db = SQLiteDatabase.openDatabase(dbf.getPath(), null, SQLiteDatabase.OPEN_READONLY);
             Cursor cur = db.rawQuery("SELECT id, code, version, name FROM cr", null)) {
            while (cur.moveToNext()) { localVer.put(cur.getInt(1), cur.getInt(2)); localRow.put(cur.getInt(1), new String[]{cur.getString(0), cur.getString(3)}); }
        }
        return diff(localVer, localRow, remote);
    }

    static JSONObject diff(Map<Integer, Integer> localVer, Map<Integer, String[]> localRow, Map<String, String[]> remote) throws Exception {
        JSONArray nw = new JSONArray(), upd = new JSONArray(), gone = new JSONArray();
        Map<Integer, String[]> best = new HashMap<>();   // код → запись с наибольшей версией
        for (String[] r : remote.values()) {
            String[] cv = r[0].split("_");
            int code = Integer.parseInt(cv[0]), ver = Integer.parseInt(cv[1]);
            String[] b = best.get(code);
            if (b == null || Integer.parseInt(b[0].split("_")[1]) < ver) best.put(code, r);
        }
        for (Map.Entry<Integer, String[]> e : best.entrySet()) {
            String[] r = e.getValue(); int ver = Integer.parseInt(r[0].split("_")[1]);
            Integer lv = localVer.get(e.getKey());
            JSONObject o = new JSONObject().put("id", r[0]).put("name", r[1]).put("date", r[2]);
            if (lv == null) nw.put(o);
            else if (ver > lv) upd.put(o.put("was", localRow.get(e.getKey())[0]));
        }
        for (Map.Entry<Integer, String[]> e : localRow.entrySet())
            if (!best.containsKey(e.getKey())) gone.put(new JSONObject().put("id", e.getValue()[0]).put("name", e.getValue()[1]));
        return new JSONObject().put("new", nw).put("upd", upd).put("gone", gone).put("remote", remote.size()).put("local", localRow.size());
    }

    // ------------------------------------------------------------------ уведомление
    private static void notifyNew(Context c, JSONObject res) throws Exception {
        SharedPreferences p = sp(c);
        Set<String> told = new HashSet<>(p.getStringSet("told", new HashSet<>()));
        int fresh = 0; String first = null;
        for (String k : new String[]{"new", "upd"}) {
            JSONArray a = res.getJSONArray(k);
            for (int i = 0; i < a.length(); i++) {
                String id = a.getJSONObject(i).getString("id");
                if (told.add(id)) { fresh++; if (first == null) first = a.getJSONObject(i).getString("name"); }
            }
        }
        if (fresh == 0) return;
        p.edit().putStringSet("told", told).apply();
        int n = res.getJSONArray("new").length(), u = res.getJSONArray("upd").length();
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;
        if (Build.VERSION.SDK_INT >= 26) nm.createNotificationChannel(new NotificationChannel(CHANNEL, "Новые клинические рекомендации", NotificationManager.IMPORTANCE_DEFAULT));
        Intent open = new Intent(c, MainActivity.class).putExtra("hash", "#krnew").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pi = PendingIntent.getActivity(c, 1, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        String title = "Клинические рекомендации: " + (n > 0 ? "новых — " + n : "") + (n > 0 && u > 0 ? ", " : "") + (u > 0 ? "обновлено — " + u : "");
        Notification nt = new Notification.Builder(c, CHANNEL)
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentTitle(title)
                .setContentText(fresh == 1 ? first : first + " и ещё " + (fresh - 1))
                .setContentIntent(pi).setAutoCancel(true).build();
        try { nm.notify(JOB_ID, nt); } catch (SecurityException ignored) { }   // нет разрешения на уведомления
    }

    // ------------------------------------------------------------------ передача в чат разработки (через Google-скрипт организатора)
    static File listFile(Context c) { return new File(c.getFilesDir(), "kr_list.json.gz"); }

    private static void saveList(Context c, String body, String op) {
        try (java.util.zip.GZIPOutputStream g = new java.util.zip.GZIPOutputStream(new java.io.FileOutputStream(listFile(c)))) {
            g.write(body.getBytes("UTF-8"));
            sp(c).edit().putString("listOp", op).apply();
        } catch (Exception ignored) { }
    }

    interface UpCb { void item(String name, boolean ok, String msg); void done(int ok, int total); }

    private static volatile boolean uploading = false;

    /** Отправить список КР (последний скачанный) и тексты КР ids на скрипт url. */
    static void upload(Context ctx, String url, String key, JSONArray ids, UpCb cb) {
        if (uploading) return;
        uploading = true;
        final Context c = ctx.getApplicationContext();
        new Thread(() -> {
            int ok = 0, total = ids.length() + 1;
            try {
                // 1. список действующих КР — исходный ответ сайта
                try {
                    File lf = listFile(c);
                    if (!lf.exists()) throw new Exception("сначала нажмите «Проверить сейчас»");
                    byte[] gz = java.nio.file.Files.readAllBytes(lf.toPath());
                    post(url, key, "list.json.gz", sp(c).getString("listOp", ""), gz);
                    ok++; cb.item("список КР", true, "");
                } catch (Exception e) { cb.item("список КР", false, msg(e)); }
                // 2. тексты КР
                for (int i = 0; i < ids.length(); i++) {
                    String id = ids.optString(i);
                    try {
                        if (!id.matches("\\d+_\\d+")) throw new Exception("неверный номер");
                        String json = Downloader.fetch(id, null).replaceAll("data:image/[a-zA-Z+]+;base64,[A-Za-z0-9+/=\\s]+", "");
                        if (!json.contains("\"sections\"")) throw new Exception("в ответе Минздрава нет текста");
                        java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
                        try (java.util.zip.GZIPOutputStream g = new java.util.zip.GZIPOutputStream(bo)) { g.write(json.getBytes("UTF-8")); }
                        post(url, key, id + ".json.gz", "GetClinrec2", bo.toByteArray());
                        ok++; cb.item(id, true, (bo.size() / 1024) + " КБ");
                    } catch (Exception e) { cb.item(id, false, msg(e)); }
                }
            } finally { uploading = false; cb.done(ok, total); }
        }).start();
    }

    private static String msg(Exception e) {
        if (e instanceof java.net.UnknownHostException || e instanceof java.net.ConnectException || e instanceof java.net.SocketTimeoutException) return "нет связи";
        return String.valueOf(e.getMessage());
    }

    @SuppressWarnings("deprecation")
    private static void post(String url, String key, String name, String src, byte[] gz) throws Exception {
        if (!url.matches("https://script\\.google\\.com/macros/s/[\\w-]+/exec")) throw new Exception("нет адреса скрипта");
        String body = new JSONObject().put("op", "kr").put("key", key).put("name", name).put("src", src)
                .put("data", android.util.Base64.encodeToString(gz, android.util.Base64.NO_WRAP)).toString();
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(20000); c.setReadTimeout(180000); c.setDoOutput(true); c.setRequestMethod("POST");
        c.setInstanceFollowRedirects(true);
        c.setRequestProperty("Content-Type", "text/plain;charset=utf-8");
        byte[] b = body.getBytes("UTF-8");
        c.setFixedLengthStreamingMode(b.length);
        try {
            try (java.io.OutputStream o = c.getOutputStream()) { o.write(b); }
            int code = c.getResponseCode();
            String resp = "";
            try (InputStream in = code < 400 ? c.getInputStream() : c.getErrorStream()) {
                if (in != null) { ByteArrayOutputStream bo = new ByteArrayOutputStream(); byte[] buf = new byte[8192]; int n; while ((n = in.read(buf)) > 0) bo.write(buf, 0, n); resp = bo.toString("UTF-8"); }
            }
            if (resp.contains("\"err\":\"key\"")) throw new Exception("скрипт не принял ключ организатора");
            if (resp.contains("\"ok\":false") || !resp.contains("\"ok\":true"))
                throw new Exception(code != 200 ? "скрипт ответил HTTP " + code : "скрипт не умеет принимать КР — обновите его код");
        } finally { c.disconnect(); }
    }

    // ------------------------------------------------------------------ сеть
    @SuppressWarnings("deprecation")
    private static String get(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(20000); c.setReadTimeout(120000); c.setUseCaches(false);
        try {
            if (c.getResponseCode() != 200) throw new Exception("сайт Минздрава ответил HTTP " + c.getResponseCode());
            ByteArrayOutputStream o = new ByteArrayOutputStream();
            try (InputStream in = c.getInputStream()) { byte[] b = new byte[16384]; int n; while ((n = in.read(b)) > 0) o.write(b, 0, n); }
            return o.toString("UTF-8");
        } finally { c.disconnect(); }
    }
}
