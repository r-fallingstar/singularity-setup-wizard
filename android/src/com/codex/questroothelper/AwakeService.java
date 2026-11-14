package com.codex.questroothelper;

import android.app.*;
import android.content.Intent;
import android.os.IBinder;
import android.os.PowerManager;

/** Keeps an already-awake screen active; never wakes a manually sleeping device. */
public class AwakeService extends Service {
  private PowerManager.WakeLock screen;

  @Override public void onCreate() {
    super.onCreate();
    NotificationManager nm=getSystemService(NotificationManager.class);
    nm.createNotificationChannel(new NotificationChannel("manual_sleep",Words.text(this,"自動スリープ停止","Manual sleep only"),NotificationManager.IMPORTANCE_LOW));
    Notification n=new Notification.Builder(this,"manual_sleep")
      .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
      .setContentTitle(Words.text(this,"自動スリープ停止","Manual sleep only"))
      .setContentText(Words.text(this,"電源ボタンでスリープ・復帰できます","Use the power button to sleep or wake"))
      .setOngoing(true).build();
    startForeground(2,n);
  }

  @Override public int onStartCommand(Intent intent,int flags,int startId) {
    if(!Compatibility.supported()){stopSelf();return START_NOT_STICKY;}
    if(intent!=null && intent.hasExtra("manual_sleep_only"))
      getSharedPreferences("power_settings",0).edit().putBoolean("manual_sleep_only",intent.getBooleanExtra("manual_sleep_only",false)).apply();
    if(!getSharedPreferences("power_settings",0).getBoolean("manual_sleep_only",false)) {
      stopSelf(); return START_NOT_STICKY;
    }
    if(screen==null) {
      PowerManager pm=getSystemService(PowerManager.class);
      // No ACQUIRE_CAUSES_WAKEUP or ON_AFTER_RELEASE flags: the power button wins.
      screen=pm.newWakeLock(PowerManager.SCREEN_BRIGHT_WAKE_LOCK,"QuestRootHelper:manual-sleep");
      screen.setReferenceCounted(false);
    }
    if(!screen.isHeld())screen.acquire();
    return START_STICKY;
  }

  @Override public void onDestroy() {
    if(screen!=null && screen.isHeld())screen.release();
    stopForeground(true);
    super.onDestroy();
  }
  @Override public IBinder onBind(Intent intent) { return null; }
}
