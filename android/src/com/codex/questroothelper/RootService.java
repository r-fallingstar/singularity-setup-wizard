package com.codex.questroothelper;
import android.app.*;
import android.content.Intent;
import android.os.IBinder;
import java.io.*;
import java.net.*;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;

public class RootService extends Service {
  private static final AtomicBoolean running=new AtomicBoolean(false);
  private void status(String s) {
    android.util.Log.i("QuestRootHelper",s);
    try { FileWriter w=new FileWriter(new File(getFilesDir(),"status.txt")); w.write(new java.util.Date()+"\n"+s+"\n"); w.close(); } catch(IOException ignored){}
  }
  private String cmd(String command) throws IOException {
    String marker="__QRH_"+UUID.randomUUID().toString().replace("-","")+"__";
    try(Socket socket=new Socket()) {
      socket.connect(new InetSocketAddress("127.0.0.1",4444),700);
      socket.setSoTimeout(5000);
      Writer w=new OutputStreamWriter(socket.getOutputStream(),"UTF-8");
      w.write(command+"\necho "+marker+"\n"); w.flush();
      BufferedReader r=new BufferedReader(new InputStreamReader(socket.getInputStream(),"UTF-8"));
      StringBuilder out=new StringBuilder(); String line;
      while((line=r.readLine())!=null){if(line.equals(marker))return out.toString().trim(); out.append(line).append('\n');}
      throw new IOException("root socket closed");
    }
  }
  private void repair(String mode) throws IOException {
    cmd("nohup setsid /data/local/tmp/quest-root-normalize /system/bin/sh /data/local/tmp/quest-root-helper.sh "+mode+" >/data/local/tmp/quest-root-helper-launch.log 2>&1 </dev/null &");
  }
  private void runOnce() {
    long end=android.os.SystemClock.elapsedRealtime()+210000;
    boolean launched=false; long daemonSeen=0;
    status("Waiting for official Singularity root (local connection only).");
    try {
      while(android.os.SystemClock.elapsedRealtime()<end) {
        try {
          if(!cmd("id -u").equals("0")) { Thread.sleep(500); continue; }
          String ready=cmd("test -f /data/adb/singularity/root-helper-ready && cmp -s /proc/sys/kernel/random/boot_id /data/adb/singularity/root-helper-ready && echo ready");
          if(ready.equals("ready")) {
            if(launched) {
              Thread.sleep(2500);
              // Clear Singularity's cached pre-root shells/UI without setting
              // Android's force-stopped flag, so its next boot receiver runs.
              cmd("kill -TERM $(pidof com.lumi.singularity) 2>/dev/null || true");
            }
            status("Root ready. Credentials normalized; protections retained."); return;
          }
          String daemon=cmd("pidof magiskd");
          if(daemon.length()>0) {
            if(daemonSeen==0) daemonSeen=android.os.SystemClock.elapsedRealtime();
            if(!launched && android.os.SystemClock.elapsedRealtime()-daemonSeen>8000){repair("repair"); launched=true; status("Normalizing Magisk credentials.");}
          } else if(!launched && !cmd("id").contains("uid=0")) {
            repair("bootstrap"); launched=true;
            status("Completing official Magisk setup with normalized credentials.");
          }
        } catch(IOException e) { /* Official root may still be starting. */ }
        Thread.sleep(500);
      }
      status("Timed out. No automatic reboot or repeated exploit is attempted.");
    } catch(InterruptedException e) { Thread.currentThread().interrupt(); status("Interrupted."); }
    finally { running.set(false); stopForeground(true); stopSelf(); }
  }
  @Override public int onStartCommand(Intent i,int f,int id) {
    NotificationManager nm=getSystemService(NotificationManager.class);
    nm.createNotificationChannel(new NotificationChannel("quest_root",Words.text(this,"rootの起動補助","Root startup assistance"),NotificationManager.IMPORTANCE_LOW));
    Notification n=new Notification.Builder(this,"quest_root").setSmallIcon(android.R.drawable.stat_sys_download_done).setContentTitle("Singularity Setup Wizard").setContentText(Words.text(this,"端末内のrootを確認中","Checking local Singularity root")).build();
    startForeground(1,n);
    if(!Compatibility.supported()){status("Unvalidated model/build: assistance disabled.");stopForeground(true);stopSelf();return START_NOT_STICKY;}
    if(running.compareAndSet(false,true))new Thread(new Runnable(){public void run(){runOnce();}},"quest-root-helper").start();
    return START_NOT_STICKY;
  }
  @Override public IBinder onBind(Intent i) { return null; }
}
