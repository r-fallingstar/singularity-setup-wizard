package com.codex.questroothelper;
import android.content.*;
public class BootReceiver extends BroadcastReceiver {
  @Override public void onReceive(Context c, Intent i) {
    if(Intent.ACTION_BOOT_COMPLETED.equals(i.getAction())) {
      if(c.getSharedPreferences("wizard",0).getBoolean("auto_root",true))c.startForegroundService(new Intent(c,RootService.class));
      if(c.getSharedPreferences("power_settings",0).getBoolean("manual_sleep_only",false))
        c.startForegroundService(new Intent(c,AwakeService.class));
    }
  }
}
